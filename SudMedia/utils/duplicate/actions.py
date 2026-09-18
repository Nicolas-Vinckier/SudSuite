"""Actions réversibles applicables aux doublons détectés."""

from __future__ import annotations

from pathlib import Path

from ..filesystem.quarantine import QuarantineResult, quarantine_files
from .models import DuplicateGroup


def _keeper(group: DuplicateGroup) -> Path:
    return min(group.files, key=lambda item: (item.modified_ns, str(item.path).lower())).path


def quarantine_duplicates(
    groups: list[DuplicateGroup], destination: str | Path
) -> QuarantineResult:
    """Déplace toutes les copies d'un groupe sauf la plus ancienne et produit un manifeste."""
    grouped_files = []
    for group in groups:
        keeper = _keeper(group)
        grouped_files.append(
            {
                "keeper": keeper,
                "duplicates": [
                    {"path": candidate.path, "size": candidate.size, "kind": group.kind}
                    for candidate in group.files
                ],
                "type": group.kind,
            }
        )

    return quarantine_files(
        grouped_files,
        destination,
        manifest_format="sudsuite-duplicate-quarantine-v1",
    )
