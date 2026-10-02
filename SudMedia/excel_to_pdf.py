"""Convertit des fichiers Excel en PDF avec une page par feuille."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SudMedia.utils import configure_console_output
from SudMedia.utils.office import (
    OfficeConversionError,
    collect_spreadsheets,
    convert_spreadsheet_to_pdf,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convertit des tableurs Excel en PDF avec une page par feuille."
    )
    parser.add_argument("paths", nargs="*", help="Fichiers Excel ou dossiers a convertir")
    parser.add_argument("-o", "--output", help="Dossier de sortie")
    parser.add_argument("--soffice", help="Chemin vers l'executable LibreOffice")
    parser.add_argument(
        "--backend",
        choices=("auto", "excel", "libreoffice"),
        default="auto",
        help="Moteur d'export (defaut : auto, Excel puis LibreOffice)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Delai maximum par fichier en secondes (defaut : 300)",
    )
    return parser


def _default_output_dir(first_source: Path) -> Path:
    return first_source.parent / f"{first_source.stem}_pdf"


def main(argv: list[str] | None = None) -> int:
    configure_console_output()
    args = build_parser().parse_args(argv)
    raw_paths = args.paths or [input("Tableur Excel ou dossier : ").strip().strip('"')]
    sources = collect_spreadsheets(raw_paths)
    if not sources:
        print("Aucun tableur Excel ou LibreOffice trouve.")
        return 1

    output_dir = Path(args.output) if args.output else _default_output_dir(sources[0])
    timeout = max(1, args.timeout)
    converted = 0
    errors: list[str] = []
    print(f"Conversion de {len(sources)} tableur(s) vers : {output_dir.resolve()}")

    for source in sources:
        try:
            result = convert_spreadsheet_to_pdf(
                source,
                output_dir,
                soffice=args.soffice,
                backend=args.backend,
                timeout=timeout,
            )
        except OfficeConversionError as error:
            errors.append(str(error))
            print(f"Erreur : {error}")
        else:
            converted += 1
            print(f"OK : {result.source.name} -> {result.output.name}")

    print("\n" + "=" * 52)
    print(f"PDF crees : {converted}")
    print(f"Erreurs : {len(errors)}")
    print(f"Sortie : {output_dir.resolve()}")
    print(f"Termine : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 52)
    return 0 if converted and not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
