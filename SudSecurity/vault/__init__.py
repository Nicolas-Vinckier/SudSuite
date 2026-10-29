"""Chiffrement de fichiers pour Sud Vault Sync."""

from .crypto import (
    CHUNK_SIZE,
    MAGIC,
    VaultError,
    create_key,
    decrypt_file,
    default_key_path,
    encrypt_file,
    load_key,
)

__all__ = [
    "CHUNK_SIZE",
    "MAGIC",
    "VaultError",
    "create_key",
    "decrypt_file",
    "default_key_path",
    "encrypt_file",
    "load_key",
]
