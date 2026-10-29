"""Modèles et exceptions du gestionnaire d'archives."""

from __future__ import annotations

from dataclasses import dataclass

from ..filesystem.paths import ExtractionBackendError


@dataclass
class Toolchain:
    sevenzip: str | None = None
    xz: str | None = None


class CompressionBackendError(RuntimeError):
    pass


__all__ = [
    "CompressionBackendError",
    "ExtractionBackendError",
    "Toolchain",
]
