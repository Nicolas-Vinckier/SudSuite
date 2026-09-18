"""Modèles et exceptions du gestionnaire d'archives."""

from __future__ import annotations

from dataclasses import dataclass

from ..filesystem.paths import ExtractionBackendError
from ..filesystem.scanner import ScannedEntry


# Alias FileEntry pointant vers ScannedEntry du filesystem
@dataclass
class FileEntry:
    path: str
    arcname: str
    size: int


@dataclass
class Toolchain:
    sevenzip: str | None = None
    xz: str | None = None


class CompressionBackendError(RuntimeError):
    pass


__all__ = [
    "CompressionBackendError",
    "ExtractionBackendError",
    "FileEntry",
    "Toolchain",
]
