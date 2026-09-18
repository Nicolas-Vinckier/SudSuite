"""Analyse et classification de la qualité de compression."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityAnalysis:
    """Niveau de qualité normalisé et estimation lisible de son impact."""

    quality: int
    estimated_loss_percent: int
    risk_level: str
    description: str


def normalize_quality(value, default: int = 75) -> int:
    """Convertit une qualité en entier compris entre 1 et 100."""
    try:
        quality = int(value)
    except (TypeError, ValueError):
        quality = int(default)
    return max(1, min(100, quality))


def analyze_quality(value, default: int = 75) -> QualityAnalysis:
    """Classe le risque visuel estimé d'un niveau de compression avec perte."""
    quality = normalize_quality(value, default)
    if quality < 50:
        risk_level = "ÉLEVÉ"
        description = "Artefacts visibles, flou et dégradation possible des couleurs."
    elif quality < 80:
        risk_level = "MODÉRÉ"
        description = "Légère perte de netteté, généralement acceptable pour le web."
    else:
        risk_level = "FAIBLE"
        description = "Perte généralement peu perceptible à l'œil nu."

    return QualityAnalysis(
        quality=quality,
        estimated_loss_percent=100 - quality,
        risk_level=risk_level,
        description=description,
    )


def print_quality_analysis(analysis: QualityAnalysis) -> None:
    """Affiche une analyse de qualité homogène dans les outils SudMedia."""
    print(
        f"[Risque {analysis.risk_level}] Qualité {analysis.quality}/100 "
        f"(perte estimée : {analysis.estimated_loss_percent} %)."
    )
    print(f"   {analysis.description}")
