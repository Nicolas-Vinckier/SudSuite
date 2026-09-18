"""Actions réversibles applicables aux doublons détectés."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from SudCore.files import atomic_write_json, unique_path

from .models import DuplicateGroup


@dataclass(frozen=True)
class QuarantineResult:
    destination: Path
    moved_files: tuple[Path, ...]
    released_bytes: int


def _keeper(group: DuplicateGroup) -> Path:
    return min(group.files, key=lambda item: (item.modified_ns, str(item.path).lower())).path


def quarantine_duplicates(
    groups: list[DuplicateGroup], destination: str | Path
) -> QuarantineResult:
    """Déplace toutes les copies sauf la plus ancienne et produit un manifeste."""
    destination = unique_path(destination)
    destination.mkdir(parents=True)
    moved: list[Path] = []
    records: list[dict[str, str | int]] = []
    released_bytes = 0

    try:
        for group_index, group in enumerate(groups, start=1):
            keeper = _keeper(group)
            group_directory = destination / f"groupe_{group_index:04d}"
            for candidate in group.files:
                if candidate.path == keeper:
                    continue
                group_directory.mkdir(parents=True, exist_ok=True)
                target = unique_path(group_directory / candidate.path.name)
                shutil.move(str(candidate.path), target)
                moved.append(target)
                released_bytes += candidate.size
                records.append(
                    {
                        "origine": str(candidate.path.resolve()),
                        "quarantaine": str(target.resolve()),
                        "conserve": str(keeper.resolve()),
                        "taille": candidate.size,
                        "type": group.kind,
                    }
                )
    finally:
        atomic_write_json(
            destination / "manifest.json",
            {
                "format": "sudsuite-duplicate-quarantine-v1",
                "created_at": datetime.now().astimezone().isoformat(),
                "files": records,
            },
        )

    return QuarantineResult(destination, tuple(moved), released_bytes)
