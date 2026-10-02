"""Conversion de feuilles de calcul vers PDF avec LibreOffice."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..filesystem import collect_target_files, unique_path

SPREADSHEET_EXTENSIONS = (".xls", ".xlsx", ".xlsm", ".ods")
PDF_EXPORT_FILTER = "calc_pdf_Export"


class OfficeConversionError(RuntimeError):
    """Erreur lors de la conversion d'un document avec LibreOffice."""


@dataclass(frozen=True)
class SpreadsheetPdfResult:
    """Résultat de la conversion d'un tableur unique."""

    source: Path
    output: Path


def find_soffice(custom_path: str | os.PathLike[str] | None = None) -> str | None:
    """Localise l'executable LibreOffice utilisable pour la conversion."""
    candidates: list[str | os.PathLike[str]] = []
    if custom_path:
        candidates.append(custom_path)
    candidates.extend(("soffice", "libreoffice"))

    if os.name == "nt":
        for variable in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(variable)
            if base:
                candidates.append(Path(base) / "LibreOffice" / "program" / "soffice.exe")

    for candidate in candidates:
        resolved = shutil.which(os.fspath(candidate))
        if resolved:
            return resolved
        path = Path(candidate).expanduser()
        if path.is_file():
            return str(path.resolve())
    return None


def find_excel() -> str | None:
    """Retourne PowerShell lorsque l'automatisation Excel est disponible."""
    if os.name != "nt":
        return None
    return shutil.which("powershell.exe") or shutil.which("powershell")


def collect_spreadsheets(paths: Iterable[str | os.PathLike[str]]) -> list[Path]:
    """Collecte les tableurs pris en charge depuis des fichiers ou dossiers."""
    return [
        Path(path)
        for path in collect_target_files(
            paths,
            SPREADSHEET_EXTENSIONS,
            item_label="un tableur pris en charge",
        )
    ]


def _pdf_export_filter() -> str:
    """Construit le filtre Calc qui ajuste chaque feuille a une page PDF."""
    options = {"SinglePageSheets": {"type": "boolean", "value": "true"}}
    return f"pdf:{PDF_EXPORT_FILTER}:{json.dumps(options, separators=(',', ':'))}"


def _office_profile_url(profile_dir: Path) -> str:
    return profile_dir.resolve().as_uri()


def _powershell_literal(value: Path) -> str:
    return str(value).replace("'", "''")


def _excel_export_command(source: Path, output: Path) -> str:
    """Construit la commande PowerShell d'export PDF pour Microsoft Excel."""
    source_literal = _powershell_literal(source)
    output_literal = _powershell_literal(output)
    return f"""
$ErrorActionPreference = 'Stop'
$excel = $null
$workbook = $null
try {{
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $workbook = $excel.Workbooks.Open('{source_literal}', 0, $true)
    foreach ($sheet in $workbook.Worksheets) {{
        $sheet.PageSetup.Zoom = $false
        $sheet.PageSetup.FitToPagesWide = 1
        $sheet.PageSetup.FitToPagesTall = 1
    }}
    $workbook.ExportAsFixedFormat(0, '{output_literal}', 0, $true, $false)
}}
finally {{
    if ($workbook -ne $null) {{
        $workbook.Close($false)
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($workbook)
    }}
    if ($excel -ne $null) {{
        $excel.Quit()
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($excel)
    }}
}}
"""


def _convert_with_excel(
    source: Path,
    output: Path,
    *,
    timeout: int,
) -> SpreadsheetPdfResult:
    executable = find_excel()
    if executable is None:
        raise OfficeConversionError("Microsoft Excel n'est pas disponible pour l'export PDF.")

    try:
        completed = subprocess.run(
            [executable, "-NoProfile", "-NonInteractive", "-Command", _excel_export_command(source, output)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise OfficeConversionError(
            f"Conversion Excel expirée après {timeout} secondes : {source.name}"
        ) from error
    except OSError as error:
        raise OfficeConversionError(f"Impossible de lancer Excel : {error}") from error

    if completed.returncode != 0 or not output.is_file():
        detail = (completed.stderr or completed.stdout or "").strip()
        message = f"Echec de conversion Excel de {source.name}"
        if completed.returncode != 0:
            message += f" (code {completed.returncode})"
        if detail:
            message += f" : {detail[-1000:]}"
        raise OfficeConversionError(message)
    return SpreadsheetPdfResult(source=source, output=output)


def _convert_with_libreoffice(
    source: Path,
    output: Path,
    *,
    soffice: str | os.PathLike[str] | None,
    timeout: int,
) -> SpreadsheetPdfResult:
    executable = find_soffice(soffice)
    if executable is None:
        raise OfficeConversionError(
            "LibreOffice est introuvable. Installez-le ou indiquez son executable avec --soffice."
        )

    with tempfile.TemporaryDirectory(prefix="sudmedia_office_") as temp_dir:
        work_dir = Path(temp_dir)
        export_dir = work_dir / "export"
        profile_dir = work_dir / "profile"
        export_dir.mkdir()
        profile_dir.mkdir()
        command = [
            os.fspath(executable),
            "--headless",
            "--nologo",
            "--nodefault",
            "--norestore",
            f"-env:UserInstallation={_office_profile_url(profile_dir)}",
            "--convert-to",
            _pdf_export_filter(),
            "--outdir",
            str(export_dir),
            str(source),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise OfficeConversionError(
                f"Conversion LibreOffice expirée après {timeout} secondes : {source.name}"
            ) from error
        except OSError as error:
            raise OfficeConversionError(
                f"Impossible de lancer LibreOffice : {error}"
            ) from error

        generated = export_dir / f"{source.stem}.pdf"
        if completed.returncode != 0 or not generated.is_file():
            detail = (completed.stderr or completed.stdout or "").strip()
            message = f"Echec de conversion LibreOffice de {source.name}"
            if completed.returncode != 0:
                message += f" (code {completed.returncode})"
            if detail:
                message += f" : {detail[-1000:]}"
            raise OfficeConversionError(message)

        shutil.move(str(generated), str(output))
    return SpreadsheetPdfResult(source=source, output=output)


def convert_spreadsheet_to_pdf(
    source: str | os.PathLike[str],
    output_dir: str | os.PathLike[str],
    *,
    soffice: str | os.PathLike[str] | None = None,
    backend: str = "auto",
    timeout: int = 300,
) -> SpreadsheetPdfResult:
    """Convertit un tableur en PDF, avec une page par feuille de calcul.

    Sous Windows, Microsoft Excel est utilisé en priorité afin de conserver le
    rendu natif. LibreOffice sert de repli portable. Les deux moteurs forcent
    chaque feuille sur une seule page sans modifier le fichier source.
    """
    source_path = Path(source).expanduser().resolve()
    if not source_path.is_file():
        raise OfficeConversionError(f"Tableur introuvable : {source_path}")
    if source_path.suffix.lower() not in SPREADSHEET_EXTENSIONS:
        raise OfficeConversionError(f"Format de tableur non pris en charge : {source_path.suffix}")

    destination_dir = Path(output_dir).expanduser().resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = unique_path(destination_dir / f"{source_path.stem}.pdf")
    normalized_backend = backend.lower()
    if normalized_backend not in {"auto", "excel", "libreoffice"}:
        raise OfficeConversionError("Le moteur doit etre auto, excel ou libreoffice.")
    if normalized_backend == "excel":
        return _convert_with_excel(source_path, destination, timeout=timeout)
    if normalized_backend == "libreoffice":
        return _convert_with_libreoffice(
            source_path, destination, soffice=soffice, timeout=timeout
        )

    if find_excel() is not None:
        try:
            return _convert_with_excel(source_path, destination, timeout=timeout)
        except OfficeConversionError as excel_error:
            try:
                return _convert_with_libreoffice(
                    source_path, destination, soffice=soffice, timeout=timeout
                )
            except OfficeConversionError as libreoffice_error:
                raise OfficeConversionError(
                    f"Conversion impossible. Excel : {excel_error}. LibreOffice : {libreoffice_error}"
                ) from libreoffice_error
    return _convert_with_libreoffice(
        source_path, destination, soffice=soffice, timeout=timeout
    )
