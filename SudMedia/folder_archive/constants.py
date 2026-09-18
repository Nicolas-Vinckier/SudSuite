"""Constantes partagees par les moteurs d'archive."""

BUFFER_SIZE = 1024 * 1024
XZ_MAGIC = b"\xfd7zXZ\x00"

EXCLUDE_PATTERNS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    ".vscode",
    ".idea",
    ".DS_Store",
    "Thumbs.db",
    "venv",
    ".next",
    "updraft",
}
