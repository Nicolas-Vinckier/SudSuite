"""Analyse exacte et visuelle des doublons."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from SudCore.files import collect_files
from SudMedia.sudmedia_utils import IMAGE_EXTENSIONS

from .hashing import content_hash, difference_hash, hamming_distance
from .models import DuplicateGroup, DuplicateReport, FileCandidate
from .similarity import HammingIndex


def _candidate(path: Path, **values) -> FileCandidate:
    stat = path.stat()
    return FileCandidate(
        path=path,
        size=stat.st_size,
        modified_ns=stat.st_mtime_ns,
        **values,
    )


def _exact_groups(
    files: list[Path], errors: list[str]
) -> tuple[list[DuplicateGroup], set[str]]:
    by_size: dict[int, list[Path]] = defaultdict(list)
    for path in files:
        try:
            by_size[path.stat().st_size].append(path)
        except OSError as error:
            errors.append(f"{path}: {error}")

    groups: list[DuplicateGroup] = []
    redundant_paths: set[str] = set()
    for same_size in by_size.values():
        if len(same_size) < 2:
            continue
        by_hash: dict[str, list[FileCandidate]] = defaultdict(list)
        for path in same_size:
            try:
                digest = content_hash(path)
                by_hash[digest].append(_candidate(path, content_hash=digest))
            except OSError as error:
                errors.append(f"{path}: {error}")
        for matches in by_hash.values():
            if len(matches) > 1:
                matches.sort(key=lambda item: (item.modified_ns, str(item.path).lower()))
                groups.append(DuplicateGroup("exact", tuple(matches)))
                redundant_paths.update(str(item.path.resolve()) for item in matches[1:])
    groups.sort(key=lambda group: group.recoverable_bytes, reverse=True)
    return groups, redundant_paths


def _similar_groups(
    files: list[Path], threshold: int, redundant_paths: set[str], errors: list[str]
) -> list[DuplicateGroup]:
    images = [
        path
        for path in files
        if path.suffix.lower() in IMAGE_EXTENSIONS
        and str(path.resolve()) not in redundant_paths
    ]
    candidates: list[FileCandidate] = []
    for path in images:
        try:
            candidates.append(_candidate(path, visual_hash=difference_hash(path)))
        except (OSError, RuntimeError, ValueError) as error:
            errors.append(f"{path}: {error}")

    parent = list(range(len(candidates)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first: int, second: int) -> None:
        first_root, second_root = find(first), find(second)
        if first_root != second_root:
            parent[second_root] = first_root

    index = HammingIndex()
    for candidate_index, candidate in enumerate(candidates):
        visual_hash = candidate.visual_hash or 0
        for neighbor_index in index.neighbors(visual_hash, threshold):
            union(candidate_index, neighbor_index)
        index.add(visual_hash, candidate_index)

    components: dict[int, list[int]] = defaultdict(list)
    for index in range(len(candidates)):
        components[find(index)].append(index)

    groups: list[DuplicateGroup] = []
    for indexes in components.values():
        if len(indexes) < 2:
            continue
        matches = tuple(candidates[index] for index in indexes)
        maximum_distance = max(
            hamming_distance(first.visual_hash or 0, second.visual_hash or 0)
            for offset, first in enumerate(matches)
            for second in matches[offset + 1 :]
        )
        groups.append(DuplicateGroup("similar", matches, maximum_distance))
    return sorted(groups, key=lambda group: len(group.files), reverse=True)


def scan_duplicates(
    paths: Iterable[str | Path],
    *,
    similar: bool = False,
    similarity_threshold: int = 6,
) -> DuplicateReport:
    """Analyse une sélection sans modifier aucun fichier."""
    if not 0 <= similarity_threshold <= 16:
        raise ValueError("Le seuil de similarité doit être compris entre 0 et 16.")
    files = collect_files(paths)
    errors: list[str] = []
    exact_groups, redundant_paths = _exact_groups(files, errors)
    similar_groups = (
        _similar_groups(files, similarity_threshold, redundant_paths, errors)
        if similar
        else []
    )
    return DuplicateReport(len(files), exact_groups, similar_groups, errors)
