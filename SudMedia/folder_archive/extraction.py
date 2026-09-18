"""Moteurs d'extraction ZIP et TAR.XZ avec controles de securite."""

import os
import shutil
import stat
import subprocess
import tarfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .constants import BUFFER_SIZE
from .models import ExtractionBackendError
from .paths import safe_member_path
from .progress import Progress
from .toolchain import (
    decode_external_output,
    describe_backend,
    run_7zip_with_progress,
    run_command,
    thread_switch_7zip,
    thread_switch_xz,
)


def inspect_zip_for_extraction(archive_path, destination):
    files = []
    total_size = 0
    with zipfile.ZipFile(archive_path, "r", allowZip64=True) as archive:
        for info in archive.infolist():
            safe_member_path(destination, info.filename)
            unix_type = (info.external_attr >> 16) & 0o170000
            if unix_type == stat.S_IFLNK:
                raise ExtractionBackendError(f"Lien symbolique refuse par securite : {info.filename}")
            if not info.is_dir():
                files.append(info)
                total_size += info.file_size
    return files, total_size


def extract_zip_python(archive_path, destination, file_infos, total_size, workers, quiet=False):
    Path(destination).mkdir(parents=True, exist_ok=False)
    progress = Progress(len(file_infos), total_size, label="Decompression", enabled=not quiet)
    progress.start()

    def extract_one(archive, info):
        target = safe_member_path(destination, info.filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        copied = 0
        with archive.open(info, "r") as source, open(target, "wb", buffering=BUFFER_SIZE) as output:
            while True:
                chunk = source.read(BUFFER_SIZE)
                if not chunk:
                    break
                output.write(chunk)
                copied += len(chunk)
                progress.update_bytes(len(chunk))
        mode = (info.external_attr >> 16) & 0o777
        if mode:
            try:
                target.chmod(mode)
            except OSError:
                pass
        progress.complete_file(max(0, info.file_size - copied))

    try:
        with zipfile.ZipFile(archive_path, "r", allowZip64=True) as archive:
            with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
                futures = [executor.submit(extract_one, archive, info) for info in file_infos]
                for future in as_completed(futures):
                    future.result()
            for info in archive.infolist():
                if info.is_dir():
                    safe_member_path(destination, info.filename).mkdir(parents=True, exist_ok=True)
        progress.finish()
    except BaseException:
        progress.abort()
        raise


def extract_zip_7zip(archive_path, destination, file_count, total_size, sevenzip, requested_threads, quiet=False):
    progress = Progress(file_count, total_size, label="Decompression", enabled=not quiet)
    command = [
        sevenzip, "x", str(archive_path), f"-o{destination}", "-y", "-bb0", "-bso0",
        *(["-bd", "-bsp0"] if quiet else ["-bsp1"]),
        thread_switch_7zip(requested_threads),
    ]
    if quiet:
        run_command(command)
    else:
        run_7zip_with_progress(command, cwd=None, progress=progress)


def extract_tar_xz_7zip(archive_path, destination, sevenzip, requested_threads, quiet=False):
    first = [sevenzip, "x", str(archive_path), "-so", "-y", "-bd", "-bb0", thread_switch_7zip(requested_threads)]
    second = [
        sevenzip, "x", "-si", "-ttar", f"-o{destination}", "-y", "-bd", "-bb0", "-bso0", "-bsp0",
        thread_switch_7zip(requested_threads),
    ]
    if not quiet:
        print("[Decompression] Extraction TAR.XZ en flux avec 7-Zip...")
    producer = subprocess.Popen(first, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    consumer = subprocess.Popen(second, stdin=producer.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    producer.stdout.close()
    consumer_error = consumer.communicate()[1]
    producer_error = producer.stderr.read()
    producer_code = producer.wait()
    if producer_code != 0 or consumer.returncode != 0:
        details = decode_external_output(producer_error + b"\n" + consumer_error).strip()
        raise ExtractionBackendError(
            "Extraction TAR.XZ avec 7-Zip echouee" + (f" : {details[-2000:]}" if details else "")
        )


def extract_tar_members(archive, destination):
    file_count = 0
    total_size = 0
    for member in archive:
        target = safe_member_path(destination, member.name)
        if member.issym() or member.islnk():
            raise ExtractionBackendError(f"Lien refuse par securite dans l'archive : {member.name}")
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if not member.isfile():
            raise ExtractionBackendError(f"Type d'entree non pris en charge : {member.name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        source = archive.extractfile(member)
        if source is None:
            raise ExtractionBackendError(f"Impossible de lire : {member.name}")
        with source, open(target, "wb", buffering=BUFFER_SIZE) as output:
            shutil.copyfileobj(source, output, length=BUFFER_SIZE)
        try:
            target.chmod(member.mode & 0o777)
            os.utime(target, (member.mtime, member.mtime))
        except OSError:
            pass
        file_count += 1
        total_size += member.size
    return file_count, total_size


def extract_tar_xz_external_xz(archive_path, destination, xz_path, requested_threads, quiet=False):
    Path(destination).mkdir(parents=True, exist_ok=False)
    if not quiet:
        print("[Decompression] XZ multithread + extraction TAR en flux...")
    env = os.environ.copy()
    env.pop("XZ_DEFAULTS", None)
    process = subprocess.Popen(
        [xz_path, "-dc", thread_switch_xz(requested_threads), str(archive_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            file_count, total_size = extract_tar_members(archive, destination)
        process.stdout.close()
        error = process.stderr.read()
        return_code = process.wait()
        if return_code != 0:
            details = decode_external_output(error).strip()
            raise ExtractionBackendError(
                f"Decompression XZ echouee (code {return_code})" + (f" : {details[-2000:]}" if details else "")
            )
        return file_count, total_size
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.wait()
        raise


def extract_tar_xz_python(archive_path, destination, quiet=False):
    Path(destination).mkdir(parents=True, exist_ok=False)
    if not quiet:
        print("[Moteur] TAR.XZ Python standard (fallback monothread)")
    with tarfile.open(archive_path, "r:xz") as archive:
        return extract_tar_members(archive, destination)


def execute_extraction(archive_format, archive_path, destination, tools, engine, requested_threads, effective_threads, quiet=False):
    if archive_format == "zip":
        file_infos, total_size = inspect_zip_for_extraction(archive_path, destination)
        if engine != "python" and tools.sevenzip:
            print(f"[Moteur] {describe_backend('7zip')}")
            extract_zip_7zip(archive_path, destination, len(file_infos), total_size, tools.sevenzip, requested_threads, quiet=quiet)
            return "7zip", len(file_infos), total_size
        if engine == "external":
            raise RuntimeError("7-Zip est requis pour une decompression ZIP externe.")
        print(f"[Moteur] Python multithread ({effective_threads} workers)")
        extract_zip_python(archive_path, destination, file_infos, total_size, effective_threads, quiet=quiet)
        return "python-multithread", len(file_infos), total_size

    if engine != "python" and tools.xz:
        print(f"[Moteur] {describe_backend('xz')}")
        file_count, total_size = extract_tar_xz_external_xz(archive_path, destination, tools.xz, requested_threads, quiet=quiet)
        return "xz", file_count, total_size
    if engine != "python" and tools.sevenzip:
        print(f"[Moteur] {describe_backend('7zip')}")
        extract_tar_xz_7zip(archive_path, destination, tools.sevenzip, requested_threads, quiet=quiet)
        return "7zip", None, None
    if engine == "external":
        raise RuntimeError("XZ ou 7-Zip est requis pour la decompression TAR.XZ externe.")
    file_count, total_size = extract_tar_xz_python(archive_path, destination, quiet=quiet)
    return "python", file_count, total_size
