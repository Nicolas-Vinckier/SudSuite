"""Résolution, sécurisation et unicité des chemins de fichiers."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path


class ExtractionBackendError(RuntimeError):
    """Erreur levée lors d'anomalies de chemin ou de décompression."""
    pass


def clean_input_path(value: str | None) -> str:
    """Nettoie un chemin saisi ou glissé-déposé dans le terminal."""
    if value is None:
        return ""

    cleaned = value.strip()
    if (
        len(cleaned) >= 2
        and cleaned[0] == cleaned[-1]
        and cleaned[0] in {'"', "'"}
    ):
        cleaned = cleaned[1:-1]
    return cleaned


def paths_overlap(first_path: str | os.PathLike[str], second_path: str | os.PathLike[str]) -> bool:
    """Indique si deux chemins sont identiques ou imbriqués l'un dans l'autre."""
    first = Path(first_path).expanduser().resolve()
    second = Path(second_path).expanduser().resolve()
    return first == second or first in second.parents or second in first.parents


def unique_path(path: str | os.PathLike[str]) -> Path:
    """Trouve un objet Path disponible sans écraser un fichier existant."""
    candidate = Path(path)
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        numbered = candidate.with_name(f"{candidate.stem}_{index}{candidate.suffix}")
        if not numbered.exists():
            return numbered
        index += 1


def unique_available_path(output_path: str | os.PathLike[str]) -> str:
    """Renvoie une chaîne de chemin libre sur le disque en ajoutant un index si nécessaire."""
    return str(unique_path(output_path))


def reserve_output_path(
    output_path: str | os.PathLike[str],
    reserved_paths: set[str] | None = None,
) -> str:
    """Réserve un nom unique au sein d'un traitement par lot en mémoire.

    Les fichiers déjà présents sur le disque ne sont pas renommés ici : chaque
    outil conserve ainsi sa politique existante (écrasement, saut ou suffixe).
    """
    candidate = Path(output_path)
    if reserved_paths is None:
        return str(candidate)

    def identity(path: Path) -> str:
        return os.path.normcase(os.path.abspath(path))

    candidate_identity = identity(candidate)
    if candidate_identity not in reserved_paths:
        reserved_paths.add(candidate_identity)
        return str(candidate)

    counter = 2
    while True:
        numbered = candidate.with_name(
            f"{candidate.stem}_{counter}{candidate.suffix}"
        )
        numbered_identity = identity(numbered)
        if numbered_identity not in reserved_paths:
            reserved_paths.add(numbered_identity)
            return str(numbered)
        counter += 1


def safe_member_path(destination: str | Path, member_name: str) -> Path:
    """Bloque les chemins absolus et les sorties de dossier (Zip Slip / Tar Slip)."""
    normalized = member_name.replace("\\", "/")
    if not normalized or normalized == ".":
        return Path(destination)
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise ExtractionBackendError(f"Chemin absolu refusé dans l'archive : {member_name}")

    target = (Path(destination) / normalized).resolve()
    root = Path(destination).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ExtractionBackendError(f"Chemin dangereux refusé dans l'archive : {member_name}")
    return target


def archive_base_name(archive_path: str | Path) -> str:
    """Retrouve le nom du dossier source depuis le nom créé à la compression."""
    name = Path(archive_path).name
    if name.lower().endswith(".tar.xz"):
        name = name[:-7]
    else:
        name = Path(name).stem

    cleaned = re.sub(r"_Archive(?:_\d{8}_\d{6})?$", "", name, flags=re.IGNORECASE)
    return cleaned or "Archive_decompressee"


def resolve_archive_output_path(
    output_input: str | Path | None,
    default_output_dir: str | Path,
    default_filename: str,
    expected_ext: str,
) -> Path:
    """Détermine le chemin de sortie final d'une archive."""
    default_output_dir = Path(default_output_dir).resolve()

    if not output_input:
        return default_output_dir / default_filename

    candidate = Path(output_input).expanduser()
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()

    if candidate.exists() and candidate.is_dir():
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate / default_filename

    if candidate.suffix:
        output_file = candidate
        if not output_file.name.lower().endswith(expected_ext.lower()):
            if expected_ext.lower() == ".tar.xz" and output_file.name.lower().endswith(".tar"):
                output_file = Path(str(output_file) + ".xz")
            else:
                output_file = output_file.with_suffix(expected_ext)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        return output_file

    candidate.mkdir(parents=True, exist_ok=True)
    return candidate / default_filename


def resolve_extraction_paths(
    archive_path: str | Path,
    destination_input: str | Path | None,
) -> tuple[Path, Path]:
    """Renvoie le dossier racine de destination et le dossier cible final."""
    if destination_input:
        destination_root = Path(destination_input).expanduser()
        if not destination_root.is_absolute():
            destination_root = Path.cwd() / destination_root
    else:
        destination_root = Path(archive_path).resolve().parent

    destination_root = destination_root.resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    final_folder = destination_root / archive_base_name(archive_path)
    return destination_root, final_folder


def detect_archive_format(archive_path: str | Path) -> str:
    """Détecte le format supporté d'une archive (.zip ou .tar.xz)."""
    name = str(archive_path).lower()
    if name.endswith(".zip"):
        return "zip"
    if name.endswith(".tar.xz") or name.endswith(".txz"):
        return "tar.xz"
    raise ValueError("Format non pris en charge. Utilisez une archive .zip, .tar.xz ou .txz.")


def make_staging_folder(destination_root: Path, final_folder: Path) -> Path:
    """Crée un dossier d'étape temporaire unique pour sécuriser l'extraction."""
    if final_folder.exists():
        raise FileExistsError(
            f"Le dossier de destination existe déjà : {final_folder}. "
            "Renommez-le, déplacez-le ou choisissez une autre destination."
        )

    for _ in range(10):
        candidate = destination_root / f"SudMedia_extraction_{uuid.uuid4().hex}"
        if not candidate.exists():
            return candidate
    raise RuntimeError("Impossible de réserver un dossier temporaire unique.")
