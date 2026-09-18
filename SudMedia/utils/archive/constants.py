"""Constantes des formats et moteurs d'archives."""

from ..filesystem.constants import EXCLUDE_PATTERNS

BUFFER_SIZE = 1024 * 1024
XZ_MAGIC = b"\xfd7zXZ\x00"

__all__ = ["BUFFER_SIZE", "EXCLUDE_PATTERNS", "XZ_MAGIC"]
