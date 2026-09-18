"""Statistiques de traitement de fichiers par lot et bilans d'opération."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from .size import SizeAnalysis, analyze_size_change, format_size


@dataclass
class ProcessingStats:
    """Statistiques communes aux traitements de fichiers par lot."""

    total_files: int
    success_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    original_size: int = 0
    final_size: int = 0
    started_at: float = field(default_factory=time.perf_counter)

    def add_success(self, original_size: int, final_size: int) -> None:
        self.success_count += 1
        self.original_size += max(0, int(original_size))
        self.final_size += max(0, int(final_size))

    def add_skipped(self) -> None:
        self.skipped_count += 1

    def add_error(self) -> None:
        self.error_count += 1

    @property
    def elapsed(self) -> float:
        return max(0.0, time.perf_counter() - self.started_at)

    @property
    def size_analysis(self) -> SizeAnalysis:
        return analyze_size_change(self.original_size, self.final_size)


def print_processing_summary(
    stats: ProcessingStats,
    *,
    title: str = "BILAN DE L'OPÉRATION",
    item_label: str = "Fichiers traités",
    original_label: str = "Taille initiale",
    final_label: str = "Taille finale",
    output_path: str | os.PathLike[str] | None = None,
    width: int = 45,
    show_duration: bool = True,
) -> None:
    """Affiche un bilan commun avec compteurs, tailles et variation."""
    analysis = stats.size_analysis
    print("\n" + "=" * width)
    print(f"📊 {title}")
    print("=" * width)
    print(f"✅ {item_label} : {stats.success_count}/{stats.total_files}")
    if stats.skipped_count:
        print(f"⏩ Fichiers ignorés : {stats.skipped_count}")
    if stats.error_count:
        print(f"⚠️  Erreurs : {stats.error_count}")
    if show_duration:
        print(f"⏱️  Temps écoulé : {stats.elapsed:.2f} secondes")
    print(f"📦 {original_label} : {format_size(stats.original_size)}")
    print(f"📦 {final_label} : {format_size(stats.final_size)}")

    if analysis.variation < 0:
        print(
            f"📉 Gain d'espace : {format_size(analysis.saved_bytes)} "
            f"({analysis.reduction_percent:.1f} %)"
        )
    elif analysis.variation > 0:
        print(
            f"📈 Augmentation : {format_size(analysis.increased_bytes)} "
            f"({abs(analysis.reduction_percent):.1f} %)"
        )
    else:
        print("➖ Variation : aucune")

    if output_path is not None:
        print(f"📂 Sortie : {output_path}")
    print("=" * width)
