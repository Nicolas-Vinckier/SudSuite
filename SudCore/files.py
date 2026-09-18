"""Primitives sûres et sans dépendance pour manipuler des fichiers."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any


DEFAULT_IGNORED_DIRECTORIES = frozenset(
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


def _normalized_extensions(extensions: Iterable[str] | None) -> tuple[str, ...] | None:
    if extensions is None:
        return None
    return tuple(
        extension.lower() if extension.startswith(".") else f".{extension.lower()}"
        for extension in extensions
    )


def collect_files(
    paths: Iterable[str | os.PathLike[str]],
    *,
    extensions: Iterable[str] | None = None,
    ignored_directories: Iterable[str] = DEFAULT_IGNORED_DIRECTORIES,
) -> list[Path]:
    """Retourne les fichiers uniques d'une sélection, dans un ordre stable."""
    accepted = _normalized_extensions(extensions)
    ignored = set(ignored_directories)
    files: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        if accepted is not None and path.suffix.lower() not in accepted:
            return
        identity = os.path.normcase(os.path.realpath(path))
        if identity not in seen:
            seen.add(identity)
            files.append(path)

    for raw_path in paths:
        path = Path(os.fspath(raw_path).strip().strip('"')).expanduser()
        if path.is_file():
            add(path)
            continue
        if not path.is_dir():
            continue

        for root, directories, filenames in os.walk(path, followlinks=False):
            directories[:] = sorted(
                name
                for name in directories
                if name not in ignored and not name.startswith((".", "__"))
            )
            for filename in sorted(filenames):
                add(Path(root) / filename)

    return files


def hash_file(
    path: str | os.PathLike[str],
    algorithm: str = "sha256",
    *,
    chunk_size: int = 1024 * 1024,
) -> str:
    """Calcule une empreinte en flux, sans charger le fichier en mémoire."""
    digest = hashlib.new(algorithm)
    with open(path, "rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def unique_path(path: str | os.PathLike[str]) -> Path:
    """Trouve un nom disponible sans écraser un fichier existant."""
    candidate = Path(path)
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        numbered = candidate.with_name(f"{candidate.stem}_{index}{candidate.suffix}")
        if not numbered.exists():
            return numbered
        index += 1


def atomic_write_json(path: str | os.PathLike[str], data: Any) -> Path:
    """Écrit un document JSON atomiquement dans son dossier de destination."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return destination
