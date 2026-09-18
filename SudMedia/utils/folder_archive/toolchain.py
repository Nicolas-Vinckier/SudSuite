"""Détection des outils externes et lancement sécurisé des commandes d'archive."""

from __future__ import annotations

import locale
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .models import CompressionBackendError, Toolchain


def find_executable(candidates):
    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
        path = Path(candidate).expanduser()
        if path.is_file():
            return str(path.resolve())
    return None


def detect_sevenzip(custom_path=None):
    candidates = [custom_path] if custom_path else []
    candidates.extend(["7zz", "7z", "7za"])
    if os.name == "nt":
        for base in [
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("LOCALAPPDATA"),
        ]:
            if base:
                candidates.extend([
                    str(Path(base) / "7-Zip" / "7z.exe"),
                    str(Path(base) / "7-Zip" / "7zz.exe"),
                ])
    return find_executable(candidates)


def detect_xz(custom_path=None):
    candidates = [custom_path] if custom_path else []
    candidates.append("xz")
    if os.name == "nt":
        for base in [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]:
            if base:
                candidates.append(str(Path(base) / "Git" / "usr" / "bin" / "xz.exe"))
        candidates.extend([r"C:\msys64\usr\bin\xz.exe", r"C:\msys32\usr\bin\xz.exe"])
    return find_executable(candidates)


def detect_toolchain(args):
    return Toolchain(
        sevenzip=detect_sevenzip(getattr(args, "sevenzip", None)),
        xz=detect_xz(getattr(args, "xz", None)),
    )


def parse_threads(value):
    cpu_count = max(1, os.cpu_count() or 1)
    if value is None or str(value).lower() == "auto":
        return 0, cpu_count
    try:
        requested = int(value)
    except (TypeError, ValueError):
        raise ValueError("--threads doit être 'auto' ou un entier >= 1")
    if requested < 1:
        raise ValueError("--threads doit être 'auto' ou un entier >= 1")
    return requested, requested


def thread_switch_7zip(requested_threads):
    return "-mmt=on" if requested_threads == 0 else f"-mmt={requested_threads}"


def thread_switch_xz(requested_threads):
    return "-T0" if requested_threads == 0 else f"-T{requested_threads}"


def safe_unlink(path):
    try:
        Path(path).unlink(missing_ok=True)
    except TypeError:
        try:
            if Path(path).exists():
                Path(path).unlink()
        except OSError:
            pass
    except OSError:
        pass


def decode_external_output(data):
    if isinstance(data, str):
        return data
    encodings = ["utf-8"]
    if os.name == "nt":
        encodings.extend(["oem", locale.getpreferredencoding(False), "mbcs"])
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeEncodeError):
            continue
    return data.decode("utf-8", errors="replace")


def build_7zip_listfile(entries):
    fd, temp_path = tempfile.mkstemp(prefix="sudmedia_7z_", suffix=".txt")
    os.close(fd)
    try:
        with open(temp_path, "w", encoding="utf-8", newline="\n") as handle:
            for entry in entries:
                if "\n" in entry.arcname or "\r" in entry.arcname:
                    raise CompressionBackendError(
                        "7-Zip via listfile ne peut pas traiter un nom contenant un retour ligne."
                    )
                handle.write(entry.arcname)
                handle.write("\n")
        return temp_path
    except Exception:
        safe_unlink(temp_path)
        raise


def run_command(command, cwd=None, env=None, stdout=None):
    process = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdout=stdout if stdout is not None else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
    )
    if process.returncode != 0:
        error = (process.stderr or "").strip()
        raise CompressionBackendError(
            f"Commande externe échouée (code {process.returncode})"
            + (f" : {error[-2000:]}" if error else "")
        )


def run_7zip_with_progress(command, cwd, progress):
    process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output_tail = bytearray()
    progress_buffer = b""
    last_percent = None
    progress.start()
    try:
        read_chunk = getattr(process.stdout, "read1", process.stdout.read)
        while True:
            chunk = read_chunk(64 * 1024)
            if not chunk:
                break
            output_tail.extend(chunk)
            if len(output_tail) > 2000:
                del output_tail[:-2000]
            scan_buffer = progress_buffer + chunk
            matches = list(re.finditer(rb"(?:^|\s)(\d{1,3})%", scan_buffer))
            if matches:
                percent = int(matches[-1].group(1))
                if percent != last_percent:
                    progress.update_external(percent)
                    last_percent = percent
            progress_buffer = scan_buffer[-16:]
        return_code = process.wait()
        if return_code != 0:
            error = decode_external_output(bytes(output_tail)).strip()
            raise CompressionBackendError(
                f"Commande externe échouée (code {return_code})"
                + (f" : {error}" if error else "")
            )
        progress.finish()
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.wait()
        progress.abort()
        raise


def describe_backend(backend):
    return {
        "7zip": "7-Zip natif multithread",
        "xz": "XZ natif multithread + TAR streamé",
        "7zip-xz": "7-Zip/XZ multithread + TAR streamé",
        "python-multithread": "Python multithread",
        "python": "Python standard (fallback)",
    }.get(backend, backend)
