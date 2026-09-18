"""Interface en ligne de commande de Sud Duplicate."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SudMedia.utils import configure_console_output, format_size
from SudMedia.utils.duplicate import quarantine_duplicates, scan_duplicates


def print_banner() -> None:
    print(r"""
  ____            _   ____              _ _           _
 / ___| _   _  __| | |  _ \ _   _ _ __ | (_) ___ __ _| |_ ___
 \___ \| | | |/ _` | | | | | | | | '_ \| | |/ __/ _` | __/ _ \
  ___) | |_| | (_| | | |_| | |_| | |_) | | | (_| (_| | ||  __/
 |____/ \__,_|\__,_| |____/ \__,_| .__/|_|_|\___\__,_|\__\___|
                                  |_|
""")


def similarity_threshold(value: str) -> int:
    try:
        threshold = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Le seuil doit être un entier.") from error
    if not 0 <= threshold <= 16:
        raise argparse.ArgumentTypeError("Le seuil doit être compris entre 0 et 16.")
    return threshold


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Détecte les fichiers en double.")
    parser.add_argument("paths", nargs="*", help="Fichiers ou dossiers à analyser")
    parser.add_argument("--similar", action="store_true", help="Chercher aussi les images similaires")
    parser.add_argument("--threshold", type=similarity_threshold, default=6, help="Distance visuelle de 0 à 16 (défaut : 6)")
    parser.add_argument("--quarantine", help="Déplacer les doublons exacts dans ce dossier")
    parser.add_argument("--yes", action="store_true", help="Confirmer la quarantaine non-interactivement")
    return parser


def _print_groups(title, groups) -> None:
    if not groups:
        return
    print(f"\n{title}")
    for index, group in enumerate(groups, start=1):
        suffix = f" — distance max {group.distance}" if group.kind == "similar" else ""
        print(f"\n  Groupe {index} ({format_size(group.recoverable_bytes)} récupérables){suffix}")
        for candidate in group.files:
            print(f"    • {candidate.path} ({format_size(candidate.size)})")


def main(argv=None) -> int:
    configure_console_output()
    print_banner()
    args = build_parser().parse_args(argv)
    paths = args.paths or [input("📂 Fichier ou dossier à analyser : ").strip().strip('"')]
    if not any(Path(path).exists() for path in paths):
        print("❌ Aucun chemin valide à analyser.")
        return 2

    print("🔍 Analyse des tailles et empreintes...")
    report = scan_duplicates(paths, similar=args.similar, similarity_threshold=args.threshold)
    _print_groups("📎 Doublons exacts", report.exact_groups)
    _print_groups("🖼️  Images visuellement similaires (à vérifier)", report.similar_groups)

    print("\n" + "=" * 52)
    print(f"📊 Fichiers analysés : {report.scanned_files}")
    print(f"📚 Groupes exacts : {len(report.exact_groups)}")
    print(f"💾 Espace récupérable sûr : {format_size(report.recoverable_bytes)}")
    if report.errors:
        print(f"⚠️  Fichiers non analysés : {len(report.errors)}")
    print("=" * 52)

    if not report.exact_groups:
        return 0
    destination = args.quarantine
    if destination is None and not args.yes:
        choice = input("\nDéplacer les copies exactes en quarantaine ? [o/N] : ").strip().lower()
        if choice not in {"o", "oui"}:
            return 0
        destination = str(
            Path.cwd() / f"SudDuplicate_Quarantaine_{datetime.now():%Y%m%d_%H%M%S}"
        )
    if args.yes and destination is None:
        destination = str(
            Path.cwd() / f"SudDuplicate_Quarantaine_{datetime.now():%Y%m%d_%H%M%S}"
        )
    if destination:
        result = quarantine_duplicates(report.exact_groups, destination)
        print(f"✅ {len(result.moved_files)} fichier(s) déplacé(s) vers {result.destination}")
        print("↩️  Le manifeste permet de retrouver chaque emplacement d'origine.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
