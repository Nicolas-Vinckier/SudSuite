"""Formatage compact de durées et de tailles pour la progression."""

from __future__ import annotations


def format_duration(seconds: float | None) -> str:
    """Formate une durée pour la progression et son estimation restante."""
    if seconds is None:
        return "--:--"
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_size_short(size_in_bytes: int | float) -> str:
    """Formate une taille de façon compacte pour les barres étroites."""
    value = float(size_in_bytes)
    for unit in ("O", "K", "M", "G", "T"):
        if abs(value) < 1024.0 or unit == "T":
            if abs(value) >= 100:
                return f"{value:.0f}{unit}"
            if abs(value) >= 10:
                return f"{value:.1f}{unit}"
            return f"{value:.2f}{unit}"
        value /= 1024.0
    raise AssertionError("Unité de taille introuvable")
