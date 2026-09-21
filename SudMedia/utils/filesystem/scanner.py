"""Parcours récursif et analyse des dossiers."""

from __future__ import annotations

import os
import time
from collections.abc import Iterable
from dataclasses import dataclass

from .constants import EXCLUDE_PATTERNS, IGNORED_DIRECTORY_NAMES


@dataclass(frozen=True)
class ScannedEntry:
    path: str
    arcname: str
    size: int


# Alias pour compatibilité
FileEntry = ScannedEntry


def _normalized_name_patterns(patterns: Iterable[str] | None) -> set[str]:
    normalized: set[str] = set()
    if not patterns:
        return normalized
    for pattern in patterns:
        value = os.fspath(pattern).strip().strip("\"'")
        if not value:
            continue
        value = value.replace("\\", "/").strip("/")
        normalized.add(value.casefold())
    return normalized


def _normalized_extensions(extensions: Iterable[str] | None) -> set[str]:
    normalized: set[str] = set()
    if not extensions:
        return normalized
    for extension in extensions:
        value = str(extension).strip().casefold()
        if not value:
            continue
        if not value.startswith("."):
            value = f".{value}"
        normalized.add(value)
    return normalized


def _relative_pattern(path: str) -> str:
    return path.replace("\\", "/").strip("/").casefold()


def _matches_named_exclusion(name: str, relative_path: str, exclusions: set[str]) -> bool:
    if not exclusions:
        return False
    return name.casefold() in exclusions or _relative_pattern(relative_path) in exclusions


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
    exclude_folders: Iterable[str] | None = None,
    exclude_files: Iterable[str] | None = None,
    exclude_extensions: Iterable[str] | None = None,
) -> tuple[list[ScannedEntry], int, list[tuple[str, str]]]:
    """Scan complet d'un dossier : retourne les entrées, la taille totale et les erreurs."""
    start = time.perf_counter()
    entries: list[ScannedEntry] = []
    total_size = 0
    skipped: list[tuple[str, str]] = []
    excluded = _normalized_name_patterns(exclude_patterns)
    excluded_folders = _normalized_name_patterns(exclude_folders)
    excluded_files = _normalized_name_patterns(exclude_files)
    excluded_extensions = _normalized_extensions(exclude_extensions)

    for root, dirs, files in os.walk(folder_path, followlinks=False):
        dirs[:] = [
            directory
            for directory in dirs
            if not directory.startswith((".", "__"))
            and not _matches_named_exclusion(
                directory,
                os.path.relpath(os.path.join(root, directory), folder_path),
                excluded | excluded_folders,
            )
        ]
        for filename in files:
            full_path = os.path.join(root, filename)
            arcname = os.path.relpath(full_path, folder_path)
            if (
                _matches_named_exclusion(filename, arcname, excluded | excluded_files)
                or os.path.splitext(filename)[1].casefold() in excluded_extensions
            ):
                continue
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
