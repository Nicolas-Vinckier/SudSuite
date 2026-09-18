"""Moteurs de compression ZIP et TAR.XZ."""

from __future__ import annotations

import os
import subprocess
import tarfile
import zipfile

from ..progress.bar import Progress, ProgressReader
from .constants import BUFFER_SIZE
from .models import CompressionBackendError
from .toolchain import (
    build_7zip_listfile,
    describe_backend,
    run_7zip_with_progress,
    run_command,
    safe_unlink,
    thread_switch_7zip,
    thread_switch_xz,
)


def compress_zip_7zip(entries, total_size, target_folder, output_path, mode, sevenzip, requested_threads, quiet=False):
    listfile = build_7zip_listfile(entries)
    safe_unlink(output_path)
    progress = Progress(len(entries), total_size, enabled=not quiet)
    try:
        method_args = ["-mm=Deflate", "-mx=1"] if mode == "1" else ["-mm=BZip2", "-mx=7"]
        command = [
            sevenzip, "a", "-tzip", str(output_path), f"@{listfile}", "-scsUTF-8", "-y", "-bb0", "-bso0",
            *(["-bd", "-bsp0"] if quiet else ["-bsp1"]),
            thread_switch_7zip(requested_threads), *method_args,
        ]
        if quiet:
            run_command(command, cwd=target_folder)
        else:
            run_7zip_with_progress(command, cwd=target_folder, progress=progress)
    finally:
        safe_unlink(listfile)


def copy_with_progress(source, destination, progress):
    copied = 0
    while True:
        chunk = source.read(BUFFER_SIZE)
        if not chunk:
            return copied
        destination.write(chunk)
        copied += len(chunk)
        progress.update_bytes(len(chunk))


def compress_zip_python(entries, total_size, output_path, mode, quiet=False):
    compression, level = (zipfile.ZIP_DEFLATED, 1) if mode == "1" else (zipfile.ZIP_BZIP2, 7)
    safe_unlink(output_path)
    progress = Progress(len(entries), total_size, enabled=not quiet)
    progress.start()
    try:
        with zipfile.ZipFile(output_path, "w", compression=compression, compresslevel=level, allowZip64=True) as archive:
            for entry in entries:
                info = zipfile.ZipInfo.from_file(entry.path, entry.arcname)
                info.compress_type = compression
                info._compresslevel = level
                with open(entry.path, "rb", buffering=BUFFER_SIZE) as source:
                    with archive.open(info, "w", force_zip64=True) as destination:
                        copied = copy_with_progress(source, destination, progress)
                progress.complete_file(max(0, entry.size - copied))
        progress.finish()
    except BaseException:
        progress.abort()
        raise


def add_entries_to_tar(tar, entries, progress):
    for entry in entries:
        info = tar.gettarinfo(entry.path, arcname=entry.arcname)
        copied = 0
        if info.isreg():
            with open(entry.path, "rb", buffering=BUFFER_SIZE) as source:
                reader = ProgressReader(source, progress)
                tar.addfile(info, fileobj=reader)
                copied = reader.bytes_read
        else:
            tar.addfile(info)
        progress.complete_file(max(0, entry.size - copied))


def stream_tar_to_process(entries, total_size, process, quiet=False):
    progress = Progress(len(entries), total_size, enabled=not quiet)
    progress.start()
    try:
        with tarfile.open(fileobj=process.stdin, mode="w|", format=tarfile.PAX_FORMAT) as tar:
            add_entries_to_tar(tar, entries, progress)
        process.stdin.close()
        process.stdin = None
        stderr = process.stderr.read() if process.stderr else ""
        return_code = process.wait()
        if return_code != 0:
            raise CompressionBackendError(
                f"Compresseur externe échoué (code {return_code})"
                + (f" : {stderr.strip()[-2000:]}" if stderr and stderr.strip() else "")
            )
        progress.finish()
    except BaseException:
        try:
            if process.stdin:
                process.stdin.close()
        except Exception:
            pass
        if process.poll() is None:
            process.kill()
        process.wait()
        progress.abort()
        raise


def compress_tar_xz_external_xz(entries, total_size, output_path, xz_path, requested_threads, quiet=False):
    safe_unlink(output_path)
    env = os.environ.copy()
    env.pop("XZ_DEFAULTS", None)
    command = [xz_path, "-c", "-6", thread_switch_xz(requested_threads)]
    with open(output_path, "wb", buffering=BUFFER_SIZE) as output_handle:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=output_handle, stderr=subprocess.PIPE, env=env)
        stream_tar_to_process(entries, total_size, process, quiet=quiet)


def compress_tar_xz_external_7zip(entries, total_size, output_path, sevenzip, requested_threads, quiet=False):
    safe_unlink(output_path)
    command = [
        sevenzip, "a", "-txz", str(output_path), "-si", "-y", "-bd", "-bb0", "-bso0", "-bsp0", "-mx=6",
        thread_switch_7zip(requested_threads),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    stream_tar_to_process(entries, total_size, process, quiet=quiet)


def compress_tar_xz_python(entries, total_size, output_path, quiet=False):
    safe_unlink(output_path)
    progress = Progress(len(entries), total_size, enabled=not quiet)
    progress.start()
    try:
        with tarfile.open(output_path, "w:xz", preset=6, format=tarfile.PAX_FORMAT) as tar:
            add_entries_to_tar(tar, entries, progress)
        progress.finish()
    except BaseException:
        progress.abort()
        raise


def select_backend(mode, engine, tools):
    if engine == "python":
        return ["python"]
    if mode in {"1", "2"}:
        external = ["7zip"] if tools.sevenzip else []
    else:
        external = []
        if tools.xz:
            external.append("xz")
        if tools.sevenzip:
            external.append("7zip-xz")
    if engine == "external":
        if not external:
            raise RuntimeError("Aucun moteur externe compatible détecté.")
        return external
    return external + ["python"]


def execute_compression(mode, backends, entries, total_size, target_folder, output_path, tools, requested_threads, quiet=False):
    for index, backend in enumerate(backends):
        try:
            print(f"[Moteur] {describe_backend(backend)}")
            if backend == "7zip":
                compress_zip_7zip(entries, total_size, target_folder, output_path, mode, tools.sevenzip, requested_threads, quiet=quiet)
            elif backend == "xz":
                compress_tar_xz_external_xz(entries, total_size, output_path, tools.xz, requested_threads, quiet=quiet)
            elif backend == "7zip-xz":
                compress_tar_xz_external_7zip(entries, total_size, output_path, tools.sevenzip, requested_threads, quiet=quiet)
            elif backend == "python":
                if mode in {"1", "2"}:
                    compress_zip_python(entries, total_size, output_path, mode, quiet=quiet)
                else:
                    compress_tar_xz_python(entries, total_size, output_path, quiet=quiet)
            else:
                raise RuntimeError(f"Backend inconnu : {backend}")
            return backend
        except Exception as exc:
            safe_unlink(output_path)
            if index < len(backends) - 1:
                print(f"[Moteur] Échec de {describe_backend(backend)} : {exc}")
                print(f"[Moteur] Bascule automatique vers {describe_backend(backends[index + 1])}...")
                continue
            raise
    raise RuntimeError("Aucun backend disponible.")
