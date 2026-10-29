"""Primitives sûres et sans dépendance pour manipuler des fichiers."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, BinaryIO


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


def clean_input_path(value: str | None) -> str:
    """Nettoie un chemin saisi ou glissé-déposé dans le terminal."""
    if value is None:
        return ""

    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1]
    return cleaned


def paths_overlap(
    first_path: str | os.PathLike[str], second_path: str | os.PathLike[str]
) -> bool:
    """Indique si deux chemins sont identiques ou imbriqués l'un dans l'autre."""
    first = Path(first_path).expanduser().resolve()
    second = Path(second_path).expanduser().resolve()
    return first == second or first in second.parents or second in first.parents


def _normalized_extensions(extensions: Iterable[str] | None) -> tuple[str, ...] | None:
    if extensions is None:
        return None
    return tuple(
        extension.lower() if extension.startswith(".") else f".{extension.lower()}"
        for extension in (str(item) for item in extensions)
    )


def collect_files(
    paths: Iterable[str | os.PathLike[str]],
    *,
    extensions: Iterable[str] | None = None,
    ignored_directories: Iterable[str] = IGNORED_DIRECTORY_NAMES,
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
        cleaned = clean_input_path(os.fspath(raw_path))
        if not cleaned:
            continue
        path = Path(cleaned).expanduser()
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


def atomic_write_bytes(
    path: str | os.PathLike[str],
    writer: Callable[[BinaryIO], object],
    *,
    mode: int | None = None,
) -> Path:
    """Écrit un fichier via ``writer(flux_binaire)`` puis le remplace atomiquement.

    ``mode`` restreint les permissions du fichier temporaire (ex. ``0o600``) avant
    qu'il ne reçoive du contenu.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        if mode is not None:
            os.chmod(temporary, mode)
        with os.fdopen(descriptor, "wb") as stream:
            writer(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def atomic_write_text(
    path: str | os.PathLike[str],
    text: str,
    encoding: str = "utf-8",
    make_unique: bool = False,
) -> Path:
    """Écrit du texte atomiquement dans son dossier de destination."""
    destination = unique_path(path) if make_unique else Path(path)
    data = text.replace("\r\n", "\n").encode(encoding)
    return atomic_write_bytes(destination, lambda stream: stream.write(data))


def atomic_write_json(
    path: str | os.PathLike[str],
    data: Any,
    encoding: str = "utf-8",
    indent: int = 2,
) -> Path:
    """Écrit un document JSON atomiquement dans son dossier de destination."""
    text = json.dumps(data, ensure_ascii=False, indent=indent, sort_keys=True) + "\n"
    return atomic_write_text(path, text, encoding)
