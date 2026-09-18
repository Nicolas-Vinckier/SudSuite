"""Façade de compatibilité."""
from SudMedia.utils.archive.toolchain import (
    Toolchain,
    build_7zip_listfile,
    decode_external_output,
    describe_backend,
    detect_sevenzip,
    detect_toolchain,
    detect_xz,
    find_executable,
    parse_threads,
    run_7zip_with_progress,
    run_command,
    safe_unlink,
    thread_switch_7zip,
    thread_switch_xz,
)

__all__ = [
    "Toolchain",
    "build_7zip_listfile",
    "decode_external_output",
    "describe_backend",
    "detect_sevenzip",
    "detect_toolchain",
    "detect_xz",
    "find_executable",
    "parse_threads",
    "run_7zip_with_progress",
    "run_command",
    "safe_unlink",
    "thread_switch_7zip",
    "thread_switch_xz",
]
