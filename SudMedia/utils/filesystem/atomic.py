"""Écritures atomiques et sécurisées de fichiers."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .paths import unique_path


def atomic_write_text(
    path: str | os.PathLike[str],
    text: str,
    encoding: str = "utf-8",
    make_unique: bool = False,
) -> Path:
    """Écrit une chaîne de caractères de façon atomique dans un fichier."""
    destination = unique_path(path) if make_unique else Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding=encoding, newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def atomic_write_json(
    path: str | os.PathLike[str],
    data: Any,
    encoding: str = "utf-8",
    indent: int = 2,
) -> Path:
    """Écrit une structure de données JSON de façon atomique dans un fichier."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding=encoding, newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=indent, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return destination
