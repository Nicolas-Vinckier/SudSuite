"""Modèles de données de Sud Duplicate."""

from __future__ import annotations

from dataclasses import dataclass, field
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
    distance: int = 0

    @property
    def recoverable_bytes(self) -> int:
        if len(self.files) < 2:
            return 0
        return sum(file.size for file in self.files) - max(
            file.size for file in self.files
        )


@dataclass
class DuplicateReport:
    scanned_files: int
    exact_groups: list[DuplicateGroup] = field(default_factory=list)
    similar_groups: list[DuplicateGroup] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def groups(self) -> list[DuplicateGroup]:
        return [*self.exact_groups, *self.similar_groups]

    @property
    def recoverable_bytes(self) -> int:
        return sum(group.recoverable_bytes for group in self.exact_groups)
