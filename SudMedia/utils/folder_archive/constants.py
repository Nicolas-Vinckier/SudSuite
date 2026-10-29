"""Constantes des formats et moteurs d'archives."""

BUFFER_SIZE = 1024 * 1024
XZ_MAGIC = b"\xfd7zXZ\x00"

__all__ = ["BUFFER_SIZE", "XZ_MAGIC"]
