"""Collecte unifiée de fichiers cibles."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from pathlib import Path

from .constants import IGNORED_DIRECTORY_NAMES
from .paths import clean_input_path
from .scanner import walk_filtered


def _normalized_extensions(extensions: Iterable[str] | None) -> tuple[str, ...] | None:
    if extensions is None:
        return None
    normalized = []
    for ext in extensions:
        clean_ext = str(ext).lower()
        if not clean_ext.startswith("."):
            clean_ext = f".{clean_ext}"
        normalized.append(clean_ext)
    return tuple(normalized)


def collect_target_files(
    paths: Iterable[str | os.PathLike[str]],
    extensions: Iterable[str],
    *,
    item_label: str = "un fichier pris en charge",
    ignored_directories: Iterable[str] = IGNORED_DIRECTORY_NAMES,
    reporter: Callable[[str], None] | None = print,
) -> list[str]:
    """Collecte récursivement des fichiers valides, sans doublon.

    Les chemins retournés conservent leur forme d'origine afin que les dossiers
    de sortie calculés par les scripts restent inchangés.
    """
    accepted = _normalized_extensions(extensions)
    if accepted is None:
        accepted = ()
    collected: list[str] = []
    seen: set[str] = set()

    def add_file(file_path: str) -> None:
        identity = os.path.normcase(os.path.realpath(file_path))
        if identity not in seen:
            seen.add(identity)
            collected.append(file_path)

    for raw_path in paths:
        path = clean_input_path(os.fspath(raw_path))
        if not path:
            continue

        if os.path.isdir(path):
            for root, _directories, filenames in walk_filtered(
                path, ignored_directories
            ):
                for filename in filenames:
                    if filename.lower().endswith(accepted):
                        add_file(os.path.join(root, filename))
        elif os.path.isfile(path):
            if path.lower().endswith(accepted):
                add_file(path)
            elif reporter:
                reporter(
                    f"⚠️  Le fichier {os.path.basename(path)} n'est pas {item_label}."
                )
        elif reporter:
            reporter(f"❌ '{path}' n'est ni un fichier ni un dossier valide.")

    return collected


def collect_files(
    paths: Iterable[str | os.PathLike[str]],
    *,
    extensions: Iterable[str] | None = None,
    ignored_directories: Iterable[str] = IGNORED_DIRECTORY_NAMES,
) -> list[Path]:
    """Retourne les fichiers uniques d'une sélection sous forme de chemins Path."""
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
        cleaned_str = clean_input_path(os.fspath(raw_path))
        if not cleaned_str:
            continue
        path = Path(cleaned_str).expanduser()
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
