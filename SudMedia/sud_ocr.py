"""Interface en ligne de commande de Sud OCR."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SudMedia.utils import configure_console_output
from SudMedia.utils.ocr import TesseractBackend, find_tesseract, process_documents


def print_banner() -> None:
    print(r"""
  ____            _    ___   ____ ____
 / ___| _   _  __| |  / _ \ / ___|  _ \
 \___ \| | | |/ _` | | | | | |   | |_) |
  ___) | |_| | (_| | | |_| | |___|  _ <
 |____/ \__,_|\__,_|  \___/ \____|_| \_\
""")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extrait le texte des images et PDF.")
    parser.add_argument("paths", nargs="*", help="Images, PDF ou dossiers")
    parser.add_argument("-o", "--output", help="Dossier de sortie")
    parser.add_argument("-l", "--language", default="fra+eng", help="Langues Tesseract (défaut : fra+eng)")
    parser.add_argument("--dpi", type=int, default=300, help="Résolution des pages PDF scannées")
    parser.add_argument("--tesseract", help="Chemin explicite vers tesseract.exe")
    return parser


def main(argv=None) -> int:
    configure_console_output()
    print_banner()
    args = build_parser().parse_args(argv)
    paths = args.paths or [input("📂 Image, PDF ou dossier : ").strip().strip('"')]
    output = Path(args.output) if args.output else Path.cwd() / (
        f"SudOCR_{datetime.now():%Y%m%d_%H%M%S}"
    )
    executable = find_tesseract(args.tesseract)
    if args.tesseract and executable is None:
        print(f"❌ Exécutable Tesseract introuvable : {args.tesseract}")
        return 2
    backend = TesseractBackend(executable) if executable else None
    if backend is None:
        print("⚠️  Tesseract absent : seuls les PDF contenant déjà du texte pourront être extraits.")

    result = process_documents(
        paths,
        output,
        backend,
        language=args.language,
        dpi=max(72, min(600, args.dpi)),
    )
    print("\n" + "=" * 52)
    print(f"✅ Documents traités : {len(result.documents)}")
    print(f"📄 Fichiers texte créés : {len(result.outputs)}")
    print(f"📂 Sortie : {output.resolve()}")
    if result.errors:
        print(f"⚠️  Erreurs : {len(result.errors)}")
        for error in result.errors:
            print(f"    • {error}")
    print("=" * 52)
    return 0 if result.documents else 1


if __name__ == "__main__":
    raise SystemExit(main())
