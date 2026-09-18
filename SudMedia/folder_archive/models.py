"""Modeles et erreurs du gestionnaire d'archives."""

from dataclasses import dataclass


@dataclass
class FileEntry:
    path: str
    arcname: str
    size: int


@dataclass
class Toolchain:
    sevenzip: str = None
    xz: str = None


class CompressionBackendError(RuntimeError):
    pass


class ExtractionBackendError(RuntimeError):
    pass
