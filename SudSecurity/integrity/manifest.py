"""Format de manifeste et vérification d'intégrité."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path, PurePosixPath

from SudCore.files import atomic_write_json, collect_files, hash_file

from .models import IntegrityIssue, IntegrityReport


FORMAT = "sudsuite-integrity-v1"
ALGORITHM = "sha256"


def _relative_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _safe_manifest_path(root: Path, relative: str) -> Path:
    portable = PurePosixPath(relative)
    if portable.is_absolute() or ".." in portable.parts or not portable.parts:
        raise ValueError(f"Chemin non sûr dans le manifeste : {relative!r}")
    candidate = root.joinpath(*portable.parts).resolve()
    if root.resolve() != candidate and root.resolve() not in candidate.parents:
        raise ValueError(f"Chemin hors du dossier contrôlé : {relative!r}")
    return candidate


def create_manifest(
    root: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
) -> dict:
    """Crée un manifeste déterministe contenant taille, date et SHA-256."""
    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise NotADirectoryError(root_path)
    output = Path(output_path).expanduser().resolve()
    files = [path for path in collect_files([root_path]) if path.resolve() != output]
    entries = []
    for path in files:
        stat = path.stat()
        entries.append(
            {
                "path": _relative_path(path, root_path),
                "size": stat.st_size,
                "modified_ns": stat.st_mtime_ns,
                "sha256": hash_file(path, ALGORITHM),
            }
        )
    entries.sort(key=lambda entry: entry["path"].casefold())
    manifest = {
        "format": FORMAT,
        "algorithm": ALGORITHM,
        "created_at": datetime.now().astimezone().isoformat(),
        "root_name": root_path.name,
        "file_count": len(entries),
        "files": entries,
    }
    atomic_write_json(output, manifest)
    return manifest


def load_manifest(path: str | os.PathLike[str]) -> dict:
    with open(path, "r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    if manifest.get("format") != FORMAT:
        raise ValueError("Format de manifeste inconnu ou non pris en charge.")
    if manifest.get("algorithm") != ALGORITHM or not isinstance(manifest.get("files"), list):
        raise ValueError("Manifeste incomplet ou algorithme non pris en charge.")
    return manifest


def verify_manifest(
    manifest_path: str | os.PathLike[str],
    root: str | os.PathLike[str],
    *,
    detect_unexpected: bool = True,
) -> IntegrityReport:
    """Vérifie les fichiers attendus et, si demandé, les ajouts inattendus."""
    manifest_file = Path(manifest_path).expanduser().resolve()
    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise NotADirectoryError(root_path)
    manifest = load_manifest(manifest_file)
    report = IntegrityReport()
    expected_paths: set[str] = set()

    for entry in manifest["files"]:
        relative = entry.get("path")
        if not isinstance(relative, str) or relative in expected_paths:
            raise ValueError("Le manifeste contient un chemin invalide ou dupliqué.")
        expected_paths.add(relative)
        target = _safe_manifest_path(root_path, relative)
        report.checked_files += 1
        if not target.is_file():
            report.issues.append(IntegrityIssue(relative, "missing", "Fichier absent"))
            continue
        try:
            stat = target.stat()
            if stat.st_size != entry.get("size"):
                detail = f"Taille attendue {entry.get('size')}, obtenue {stat.st_size}"
                report.issues.append(IntegrityIssue(relative, "modified", detail))
                continue
            actual_hash = hash_file(target, ALGORITHM)
        except OSError as error:
            report.issues.append(IntegrityIssue(relative, "error", str(error)))
            continue
        if actual_hash != entry.get("sha256"):
            report.issues.append(IntegrityIssue(relative, "modified", "Empreinte SHA-256 différente"))
        else:
            report.unchanged_files += 1

    if detect_unexpected:
        for path in collect_files([root_path]):
            if path.resolve() == manifest_file:
                continue
            relative = _relative_path(path, root_path)
            if relative not in expected_paths:
                report.issues.append(IntegrityIssue(relative, "unexpected", "Fichier ajouté depuis le manifeste"))
    return report
