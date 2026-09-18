"""Gestion générique de mise en quarantaine de fichiers avec manifeste."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .atomic import atomic_write_json
from .paths import unique_path


@dataclass(frozen=True)
class QuarantineResult:
    destination: Path
    moved_files: tuple[Path, ...]
    released_bytes: int


def quarantine_files(
    grouped_files: list[dict[str, Any]],
    destination: str | Path,
    manifest_format: str = "sudsuite-quarantine-v1",
) -> QuarantineResult:
    """Déplace des fichiers vers un dossier de quarantaine et génère un manifeste réversible.

    ``grouped_files`` est une liste de groupes ou d'entrées contenant :
    - 'keeper': Path du fichier conservé
    - 'duplicates': liste d'objets ou dictionnaires contenant au moins 'path' et 'size'
    - optionnel 'group_id', 'type'
    """
    dest_path = unique_path(destination)
    dest_path.mkdir(parents=True, exist_ok=True)
    moved: list[Path] = []
    records: list[dict[str, Any]] = []
    released_bytes = 0

    try:
        for group_idx, group in enumerate(grouped_files, start=1):
            keeper = group.get("keeper")
            group_dir = dest_path / f"groupe_{group_idx:04d}"
            duplicates = group.get("duplicates", [])

            for item in duplicates:
                source_path = Path(item["path"] if isinstance(item, dict) else getattr(item, "path"))
                size = int(item["size"] if isinstance(item, dict) else getattr(item, "size", 0))
                kind = str(item.get("kind", group.get("type", "duplicate")) if isinstance(item, dict) else getattr(item, "kind", group.get("type", "duplicate")))

                if keeper and source_path.resolve() == Path(keeper).resolve():
                    continue

                group_dir.mkdir(parents=True, exist_ok=True)
                target = unique_path(group_dir / source_path.name)
                shutil.move(str(source_path), target)
                moved.append(target)
                released_bytes += size
                records.append(
                    {
                        "origine": str(source_path.resolve()),
                        "quarantaine": str(target.resolve()),
                        "conserve": str(Path(keeper).resolve()) if keeper else None,
                        "taille": size,
                        "type": kind,
                    }
                )
    finally:
        atomic_write_json(
            dest_path / "manifest.json",
            {
                "format": manifest_format,
                "created_at": datetime.now().astimezone().isoformat(),
                "files": records,
            },
        )

    return QuarantineResult(dest_path, tuple(moved), released_bytes)
