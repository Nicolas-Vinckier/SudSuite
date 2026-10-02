"""Interface en ligne de commande de Sud DOCX Optimizer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SudMedia.utils import configure_console_output, format_size
from SudMedia.utils.office import (
    DocxOptimizationError,
    collect_docx,
    optimize_docx,
)


def print_banner() -> None:
    print(r"""
  ____            _   ____   ___   ______  __
 / ___| _   _  __| | |  _ \ / _ \ / ___\ \/ /
 \___ \| | | |/ _` | | | | | | | | |    \  /
  ___) | |_| | (_| | | |_| | |_| | |___ /  \
 |____/ \__,_|\__,_| |____/ \___/ \____/_/\_\
                 Optimizer
""")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Optimise la taille des DOCX en traitant intelligemment leurs images internes."
    )
    parser.add_argument("paths", nargs="*", help="Fichiers DOCX ou dossiers à analyser")
    parser.add_argument(
        "-o",
        "--output",
        help="Fichier de sortie (un seul DOCX) ou dossier de sortie (lot)",
    )
    parser.add_argument(
        "--mode",
        choices=("lossless", "smart", "aggressive"),
        default=None,
        help="lossless=sans perte, smart=recommandé, aggressive=gain maximum",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=85,
        help="Qualité JPEG de 1 à 100 (défaut : 85)",
    )
    parser.add_argument(
        "--min-gain",
        type=float,
        default=None,
        help="Gain minimum en %% avant conversion/recompression avec perte",
    )
    return parser


def _interactive_mode() -> str:
    print("\n🎚️  MODE D'OPTIMISATION")
    print("1. Sans perte  : recompression PNG uniquement")
    print("2. Intelligent : PNG + conversion JPEG prudente (recommandé)")
    print("3. Agressif    : tous les PNG opaques + JPEG existants")
    choice = input("Votre choix [2] : ").strip() or "2"
    return {"1": "lossless", "2": "smart", "3": "aggressive"}.get(choice, "smart")


def _default_min_gain(mode: str) -> float:
    if mode == "aggressive":
        return 1.0
    if mode == "lossless":
        return 0.0
    return 10.0


def _resolve_output(source: Path, output_arg: str | None, multiple: bool) -> Path | None:
    if not output_arg:
        return None
    output = Path(output_arg).expanduser()
    if multiple or output.suffix.lower() != ".docx":
        output.mkdir(parents=True, exist_ok=True)
        return output / f"{source.stem}_Optimized.docx"
    return output


def _print_change_summary(result) -> None:
    print(f"   Médias internes       : {result.media_total}")
    print(f"   Médias optimisés      : {result.changed_media}")
    print(f"   PNG -> JPEG           : {result.png_to_jpeg}")
    print(f"   PNG sans perte        : {result.png_lossless}")
    print(f"   JPEG recompressés     : {result.jpeg_recompressed}")
    print(f"   Taille avant          : {format_size(result.original_size)}")
    print(f"   Taille après          : {format_size(result.optimized_size)}")
    if result.saved_bytes > 0:
        print(
            f"   ✅ Gain                : {format_size(result.saved_bytes)} "
            f"({result.reduction_percent:.2f} %)"
        )
    elif result.saved_bytes == 0:
        print("   ℹ️  Gain                : aucun changement utile")
    else:
        print(
            f"   ⚠️  Variation           : +{format_size(-result.saved_bytes)} "
            f"({-result.reduction_percent:.2f} %)"
        )


def main(argv: list[str] | None = None) -> int:
    configure_console_output()
    print_banner()
    args = build_parser().parse_args(argv)

    interactive = not args.paths
    raw_paths = args.paths or [
        input("📄 DOCX ou dossier à optimiser : ").strip().strip('"')
    ]
    sources = collect_docx(raw_paths)
    if not sources:
        print("❌ Aucun fichier DOCX trouvé.")
        return 1

    mode = args.mode or (_interactive_mode() if interactive else "smart")
    min_gain = args.min_gain if args.min_gain is not None else _default_min_gain(mode)
    quality = args.quality

    print("\n🔒 L'original ne sera jamais modifié.")
    print(f"⚙️  Mode : {mode} | qualité JPEG : {quality} | gain min. : {min_gain:g} %")

    successes = 0
    errors = 0
    total_before = 0
    total_after = 0
    multiple = len(sources) > 1

    for source in sources:
        print(f"\n{'=' * 60}")
        print(f"📄 {source}")
        try:
            result = optimize_docx(
                source,
                _resolve_output(source, args.output, multiple),
                mode=mode,
                jpeg_quality=quality,
                min_savings_percent=min_gain,
            )
        except DocxOptimizationError as error:
            errors += 1
            print(f"❌ {error}")
            continue

        successes += 1
        total_before += result.original_size
        total_after += result.optimized_size
        _print_change_summary(result)
        print(f"   📂 Sortie              : {result.output}")
        print("   🔎 Intégrité DOCX      : vérifiée")

    print(f"\n{'=' * 60}")
    print("📊 BILAN SUD DOCX OPTIMIZER")
    print(f"   Documents réussis     : {successes}")
    print(f"   Erreurs               : {errors}")
    if successes:
        print(f"   Taille totale avant   : {format_size(total_before)}")
        print(f"   Taille totale après   : {format_size(total_after)}")
        if total_before > total_after:
            saved = total_before - total_after
            percent = (saved / total_before) * 100 if total_before else 0.0
            print(f"   ✅ Gain total          : {format_size(saved)} ({percent:.2f} %)")
    print("=" * 60)
    return 0 if successes and not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
