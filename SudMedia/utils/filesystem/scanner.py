"""Parcours récursif et analyse des dossiers."""

from __future__ import annotations

import os
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .constants import EXCLUDE_PATTERNS, IGNORED_DIRECTORY_NAMES


@dataclass(frozen=True)
class ScannedEntry:
    path: str
    arcname: str
    size: int


# Alias pour compatibilité
FileEntry = ScannedEntry


def walk_filtered(
    root_path: str | os.PathLike[str],
    ignored_directories: Iterable[str] = IGNORED_DIRECTORY_NAMES,
):
    """Parcourt un dossier en ignorant les répertoires techniques et cachés."""
    ignored = set(ignored_directories)
    for root, directories, filenames in os.walk(root_path, followlinks=False):
        directories[:] = sorted(
            directory
            for directory in directories
            if directory not in ignored
            and not directory.startswith((".", "__"))
        )
        yield root, directories, sorted(filenames)


def scan_folder(
    folder_path: str | os.PathLike[str],
    quiet: bool = False,
    exclude_patterns: Iterable[str] = EXCLUDE_PATTERNS,
) -> tuple[list[ScannedEntry], int, list[tuple[str, str]]]:
    """Scan complet d'un dossier : retourne les entrées, la taille totale et les erreurs."""
    start = time.perf_counter()
    entries: list[ScannedEntry] = []
    total_size = 0
    skipped: list[tuple[str, str]] = []
    excluded = set(exclude_patterns)

    for root, dirs, files in os.walk(folder_path, followlinks=False):
        dirs[:] = [d for d in dirs if d not in excluded and not d.startswith((".", "__"))]
        for filename in files:
            if filename in excluded:
                continue
            full_path = os.path.join(root, filename)
            arcname = os.path.relpath(full_path, folder_path)
            try:
                size = os.path.getsize(full_path)
            except OSError as exc:
                skipped.append((full_path, str(exc)))
                continue
            entries.append(ScannedEntry(full_path, arcname, size))
            total_size += size

    if not quiet:
        print(f"[Analyse] Scan unique terminé en {time.perf_counter() - start:.2f} s.")
    return entries, total_size, skipped


def remove_output_from_entries(
    entries: list[ScannedEntry], output_path: str | os.PathLike[str]
) -> tuple[list[ScannedEntry], int]:
    """Évite qu'une archive de sortie existante dans le dossier source soit auto-incluse."""
    output_real = os.path.normcase(os.path.realpath(str(output_path)))
    filtered: list[ScannedEntry] = []
    removed_size = 0
    for entry in entries:
        if os.path.normcase(os.path.realpath(entry.path)) == output_real:
            removed_size += entry.size
        else:
            filtered.append(entry)
    return filtered, removed_size
