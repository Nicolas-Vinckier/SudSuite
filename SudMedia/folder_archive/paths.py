"""Resolution des chemins, scan des sources et securite d'extraction."""

import os
import re
import time
import uuid
from pathlib import Path

from .constants import EXCLUDE_PATTERNS
from .models import ExtractionBackendError, FileEntry


def resolve_archive_output_path(output_input, default_output_dir, default_filename, expected_ext):
    default_output_dir = Path(default_output_dir).resolve()

    if not output_input:
        return default_output_dir / default_filename

    candidate = Path(output_input).expanduser()
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()

    if candidate.exists() and candidate.is_dir():
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate / default_filename

    if candidate.suffix:
        output_file = candidate
        if not output_file.name.lower().endswith(expected_ext.lower()):
            if expected_ext.lower() == ".tar.xz" and output_file.name.lower().endswith(".tar"):
                output_file = Path(str(output_file) + ".xz")
            else:
                output_file = output_file.with_suffix(expected_ext)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        return output_file

    candidate.mkdir(parents=True, exist_ok=True)
    return candidate / default_filename


def archive_base_name(archive_path):
    """Retrouve le nom du dossier source depuis le nom cree a la compression."""
    name = Path(archive_path).name
    if name.lower().endswith(".tar.xz"):
        name = name[:-7]
    else:
        name = Path(name).stem

    cleaned = re.sub(r"_Archive(?:_\d{8}_\d{6})?$", "", name, flags=re.IGNORECASE)
    return cleaned or "Archive_decompressee"


def resolve_extraction_paths(archive_path, destination_input):
    """Renvoie le parent choisi et le dossier final sans le suffixe _Archive."""
    if destination_input:
        destination_root = Path(destination_input).expanduser()
        if not destination_root.is_absolute():
            destination_root = Path.cwd() / destination_root
    else:
        destination_root = Path(archive_path).resolve().parent

    destination_root = destination_root.resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    final_folder = destination_root / archive_base_name(archive_path)
    return destination_root, final_folder


def detect_archive_format(archive_path):
    name = str(archive_path).lower()
    if name.endswith(".zip"):
        return "zip"
    if name.endswith(".tar.xz") or name.endswith(".txz"):
        return "tar.xz"
    raise ValueError("Format non pris en charge. Utilisez une archive .zip, .tar.xz ou .txz.")


def safe_member_path(destination, member_name):
    """Bloque les chemins absolus et les sorties de dossier (Zip Slip/Tar Slip)."""
    normalized = member_name.replace("\\", "/")
    if not normalized or normalized == ".":
        return Path(destination)
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise ExtractionBackendError(f"Chemin absolu refuse dans l'archive : {member_name}")

    target = (Path(destination) / normalized).resolve()
    root = Path(destination).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ExtractionBackendError(f"Chemin dangereux refuse dans l'archive : {member_name}")
    return target


def make_staging_folder(destination_root, final_folder):
    if final_folder.exists():
        raise FileExistsError(
            f"Le dossier de destination existe deja : {final_folder}. "
            "Renommez-le, deplacez-le ou choisissez une autre destination."
        )

    for _ in range(10):
        candidate = destination_root / f"SudMedia_extraction_{uuid.uuid4().hex}"
        if not candidate.exists():
            return candidate
    raise RuntimeError("Impossible de reserver un dossier temporaire unique.")


def scan_folder(folder_path, quiet=False):
    """Un seul scan : taille + nombre + liste reutilisee pour la compression."""
    start = time.perf_counter()
    entries = []
    total_size = 0
    skipped = []

    for root, dirs, files in os.walk(folder_path, followlinks=False):
        dirs[:] = [directory for directory in dirs if directory not in EXCLUDE_PATTERNS]
        for filename in files:
            if filename in EXCLUDE_PATTERNS:
                continue
            full_path = os.path.join(root, filename)
            arcname = os.path.relpath(full_path, folder_path)
            try:
                size = os.path.getsize(full_path)
            except OSError as exc:
                skipped.append((full_path, str(exc)))
                continue
            entries.append(FileEntry(full_path, arcname, size))
            total_size += size

    if not quiet:
        print(f"[Analyse] Scan unique termine en {time.perf_counter() - start:.2f} s.")
    return entries, total_size, skipped


def remove_output_from_entries(entries, output_path):
    """Evite qu'une archive existante dans le dossier source s'auto-inclue."""
    output_real = os.path.normcase(os.path.realpath(str(output_path)))
    filtered = []
    removed_size = 0
    for entry in entries:
        if os.path.normcase(os.path.realpath(entry.path)) == output_real:
            removed_size += entry.size
        else:
            filtered.append(entry)
    return filtered, removed_size
