"""Modèles de données pour l'analyse des doublons."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileCandidate:
    path: Path
    size: int
    modified_ns: int
    content_hash: str | None = None
    visual_hash: int | None = None


@dataclass(frozen=True)
class DuplicateGroup:
    kind: str
    files: tuple[FileCandidate, ...]
    distance: int | None = None

    @property
    def recoverable_bytes(self) -> int:
        if len(self.files) <= 1:
            return 0
        return sum(item.size for item in self.files[1:])


@dataclass(frozen=True)
class DuplicateReport:
    scanned_files: int
    exact_groups: list[DuplicateGroup]
    similar_groups: list[DuplicateGroup]
    errors: list[str]

    @property
    def recoverable_bytes(self) -> int:
        return sum(group.recoverable_bytes for group in self.exact_groups)

    @property
    def exact_recoverable_bytes(self) -> int:
        return self.recoverable_bytes
