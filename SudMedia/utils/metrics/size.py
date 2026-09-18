"""Analyse des tailles et calculs de gains d'espace."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SizeAnalysis:
    """Comparaison réutilisable entre une taille source et une taille finale."""

    original_size: int
    final_size: int

    @property
    def variation(self) -> int:
        return self.final_size - self.original_size

    @property
    def saved_bytes(self) -> int:
        return max(0, -self.variation)

    @property
    def increased_bytes(self) -> int:
        return max(0, self.variation)

    @property
    def reduction_percent(self) -> float:
        if self.original_size <= 0:
            return 0.0
        return ((self.original_size - self.final_size) / self.original_size) * 100


def format_size(size_in_bytes: int | float) -> str:
    """Formate un nombre d'octets avec les unités françaises de SudMedia."""
    value = float(size_in_bytes)
    for unit in ("O", "Ko", "Mo", "Go", "To"):
        if abs(value) < 1024.0 or unit == "To":
            return f"{value:.2f} {unit}"
        value /= 1024.0

    raise AssertionError("Unité de taille introuvable")


def analyze_size_change(original_size: int, final_size: int) -> SizeAnalysis:
    """Calcule le gain, l'augmentation et le pourcentage entre deux tailles."""
    return SizeAnalysis(
        original_size=max(0, int(original_size)),
        final_size=max(0, int(final_size)),
    )
