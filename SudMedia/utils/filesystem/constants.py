"""Constantes relatives au système de fichiers."""

IGNORED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".idea",
        ".next",
        ".venv",
        ".vscode",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "venv",
    }
)

DEFAULT_IGNORED_DIRECTORIES = IGNORED_DIRECTORY_NAMES
EXCLUDE_PATTERNS = IGNORED_DIRECTORY_NAMES
