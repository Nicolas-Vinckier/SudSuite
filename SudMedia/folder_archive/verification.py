"""Verification rapide ou complete des archives produites."""

import lzma
import os
import time
import zipfile

from .constants import BUFFER_SIZE, XZ_MAGIC
from .toolchain import run_command, thread_switch_xz


def quick_verify_zip(output_path, expected_count):
    with zipfile.ZipFile(output_path, "r", allowZip64=True) as archive:
        count = sum(1 for item in archive.infolist() if not item.is_dir())
        if count != expected_count:
            raise RuntimeError(f"ZIP incomplet : {count} fichier(s), {expected_count} attendu(s).")


def full_verify_zip(output_path, expected_count):
    with zipfile.ZipFile(output_path, "r", allowZip64=True) as archive:
        count = sum(1 for item in archive.infolist() if not item.is_dir())
        if count != expected_count:
            raise RuntimeError(f"ZIP incomplet : {count} fichier(s), {expected_count} attendu(s).")
        bad_file = archive.testzip()
        if bad_file:
            raise RuntimeError(f"Archive ZIP corrompue au fichier : {bad_file}")


def quick_verify_xz(output_path):
    if os.path.getsize(output_path) < len(XZ_MAGIC):
        raise RuntimeError("Archive TAR.XZ vide ou tronquee.")
    with open(output_path, "rb") as handle:
        if handle.read(len(XZ_MAGIC)) != XZ_MAGIC:
            raise RuntimeError("Signature XZ invalide.")
    with lzma.open(output_path, "rb") as handle:
        handle.read(1024)


def full_verify_xz(output_path, xz_path=None, requested_threads=0):
    if xz_path:
        env = os.environ.copy()
        env.pop("XZ_DEFAULTS", None)
        run_command([xz_path, "-t", thread_switch_xz(requested_threads), str(output_path)], env=env)
        return
    with lzma.open(output_path, "rb") as handle:
        while handle.read(BUFFER_SIZE):
            pass


def verify_archive(output_path, mode, verify_mode, expected_count, tools, requested_threads):
    if verify_mode == "none":
        print("[Verification] Ignoree (--verify none) pour la vitesse maximale.")
        return
    start = time.perf_counter()
    print(f"[Verification] Mode {verify_mode}...")
    if mode in {"1", "2"}:
        (quick_verify_zip if verify_mode == "quick" else full_verify_zip)(output_path, expected_count)
    elif verify_mode == "quick":
        quick_verify_xz(output_path)
    else:
        full_verify_xz(output_path, xz_path=tools.xz, requested_threads=requested_threads)
    print(f"[Verification] OK en {time.perf_counter() - start:.2f} s.")
