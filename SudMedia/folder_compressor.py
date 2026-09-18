"""CLI du compresseur de dossiers SudMedia.

La logique reusable est repartie dans ``SudMedia.folder_archive``. Les imports
restent exposes ici pour conserver la compatibilite avec l'ancien module.
"""

import argparse
import datetime
import os
import shutil
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SudMedia.utils.archive import (
    CompressionBackendError,
    ExtractionBackendError,
    FileEntry,
    Toolchain,
    compress_tar_xz_external_7zip,
    compress_tar_xz_external_xz,
    compress_tar_xz_python,
    compress_zip_7zip,
    compress_zip_python,
    describe_backend,
    detect_sevenzip,
    detect_toolchain,
    detect_xz,
    execute_compression,
    execute_extraction,
    extract_tar_members,
    extract_tar_xz_7zip,
    extract_tar_xz_external_xz,
    extract_tar_xz_python,
    extract_zip_7zip,
    extract_zip_python,
    full_verify_xz,
    full_verify_zip,
    parse_threads,
    quick_verify_xz,
    quick_verify_zip,
    select_backend,
    verify_archive,
)
from SudMedia.utils.archive.compression import (
    add_entries_to_tar,
    copy_with_progress,
    stream_tar_to_process,
)
from SudMedia.utils.archive.extraction import inspect_zip_for_extraction
from SudMedia.utils.archive.toolchain import (
    build_7zip_listfile,
    decode_external_output,
    find_executable,
    run_7zip_with_progress,
    run_command,
    safe_unlink,
    thread_switch_7zip,
    thread_switch_xz,
)
from SudMedia.utils.console import configure_console_output
from SudMedia.utils.filesystem import (
    archive_base_name,
    clean_input_path,
    detect_archive_format,
    make_staging_folder,
    remove_output_from_entries,
    resolve_archive_output_path,
    resolve_extraction_paths,
    safe_member_path,
    scan_folder,
)
from SudMedia.utils.metrics import analyze_size_change, format_size
from SudMedia.utils.progress import (
    Progress,
    ProgressReader,
    format_duration,
    format_size_short,
)


def print_diagnostics(tools, requested_threads, effective_threads):
    print("\n" + "=" * 60)
    print("DIAGNOSTIC PERFORMANCE")
    print("=" * 60)
    print(f"CPU logique       : {max(1, os.cpu_count() or 1)}")
    print(f"Threads demandes  : {'auto' if requested_threads == 0 else requested_threads}")
    print(f"Threads cibles    : {effective_threads}")
    print(f"7-Zip             : {tools.sevenzip or 'non detecte'}")
    print(f"XZ                : {tools.xz or 'non detecte'}")
    print("=" * 60)


def _resolved_input_path(raw_path):
    path = Path(clean_input_path(raw_path)).expanduser()
    return (path if path.is_absolute() else Path.cwd() / path).resolve()


def decompress_archive(cli_args=None):
    configure_console_output()
    quiet = bool(getattr(cli_args, "quiet", False))
    raw_input = cli_args.input if cli_args and cli_args.input else input(
        "📦 Archive a decompresser (.zip ou .tar.xz) : "
    )
    archive_path = _resolved_input_path(raw_input)
    if not archive_path.is_file():
        print(f"[Erreur] '{archive_path}' n'est pas une archive valide.")
        return 2
    try:
        archive_format = detect_archive_format(archive_path)
        requested_threads, effective_threads = parse_threads(getattr(cli_args, "threads", "auto"))
    except ValueError as exc:
        print(f"[Erreur] {exc}")
        return 2

    tools = detect_toolchain(cli_args)
    if getattr(cli_args, "diagnostic", False):
        print_diagnostics(tools, requested_threads, effective_threads)
    if cli_args and cli_args.output is not None:
        destination_input = clean_input_path(cli_args.output)
    else:
        destination_input = clean_input_path(input(
            "Dossier parent de destination (Entree = a cote de l'archive) : "
        ))
    try:
        destination_root, final_folder = resolve_extraction_paths(archive_path, destination_input)
        staging_folder = make_staging_folder(destination_root, final_folder)
    except Exception as exc:
        print(f"[Erreur] Impossible de preparer la destination : {exc}")
        return 2

    print("\n" + "=" * 60)
    print("DECOMPRESSION")
    print("=" * 60)
    print(f"[Source] {archive_path}")
    print(f"[Destination] {final_folder}")
    print(f"[Format] {archive_format.upper()}")
    print(f"[Threads] {'auto' if requested_threads == 0 else requested_threads} (CPU logique : {effective_threads})")
    started_at = time.perf_counter()
    try:
        used_backend, file_count, total_size = execute_extraction(
            archive_format, archive_path, staging_folder, tools,
            getattr(cli_args, "engine", "auto"), requested_threads,
            effective_threads, quiet=quiet,
        )
        staging_folder.replace(final_folder)
        print("\n" + "=" * 60)
        print("DECOMPRESSION TERMINEE")
        print("=" * 60)
        print(f"Moteur             : {describe_backend(used_backend)}")
        print(f"Temps total         : {time.perf_counter() - started_at:.2f} s")
        if total_size is not None:
            print(f"Taille extraite     : {format_size(total_size)}")
        if file_count is not None:
            print(f"Fichiers            : {file_count}")
        print(f"Emplacement         : {final_folder}")
        print("=" * 60)
        return 0
    except KeyboardInterrupt:
        shutil.rmtree(staging_folder, ignore_errors=True)
        print("\n[Interruption] Operation annulee. Extraction partielle supprimee.")
        return 130
    except Exception as exc:
        shutil.rmtree(staging_folder, ignore_errors=True)
        print(f"\n[Erreur Fatale] {exc}")
        return 1


def _compression_mode(mode):
    return {"1": (".zip", "Classique"), "2": (".zip", "Medium"), "3": (".tar.xz", "Ultra")}.get(
        mode, (None, None)
    )


def compress_folder(cli_args=None):
    configure_console_output()
    print("\n        SUDMEDIA FOLDER COMPRESSOR - FAST ENGINE\n")
    quiet = bool(getattr(cli_args, "quiet", False))
    target_folder = clean_input_path(
        cli_args.input if cli_args and cli_args.input else input(
            "📂 Dossier a compresser (glissez-deposez ou nom) : "
        )
    )
    if not os.path.isdir(target_folder):
        print(f"[Erreur] '{target_folder}' n'est pas un dossier valide.")
        return 2
    target_folder = str(Path(target_folder).resolve())
    folder_name = os.path.basename(os.path.normpath(target_folder))
    try:
        requested_threads, effective_threads = parse_threads(getattr(cli_args, "threads", "auto"))
    except ValueError as exc:
        print(f"[Erreur] {exc}")
        return 2

    tools = detect_toolchain(cli_args)
    if getattr(cli_args, "diagnostic", False):
        print_diagnostics(tools, requested_threads, effective_threads)
    print(f"\n[Analyse] Dossier : {folder_name}")
    entries, total_size, skipped = scan_folder(target_folder, quiet=quiet)
    print(f"[Analyse] Taille a traiter : {format_size(total_size)} ({len(entries)} fichiers)")
    print(f"[Analyse] CPU : {max(1, os.cpu_count() or 1)} thread(s) logique(s)")
    print(f"[Detection] 7-Zip: {tools.sevenzip or 'absent -> fallback Python pour ZIP'}")
    print(f"[Detection] XZ: {tools.xz or 'absent -> 7-Zip XZ ou fallback Python pour TAR.XZ'}")
    if skipped:
        print(f"[Attention] {len(skipped)} fichier(s) impossible(s) a analyser et ignores.")
        for path, error in skipped[:5]:
            print(f"  - {path}: {error}")

    mode = cli_args.mode if cli_args and cli_args.mode else None
    if not mode:
        print("\n1. CLASSIQUE - ZIP Deflate, priorite vitesse")
        print("2. MEDIUM    - ZIP BZip2, meilleur gain d'espace")
        print("3. ULTRA     - TAR.XZ / LZMA2, multithread si possible")
        mode = input("\nVotre choix (1, 2 ou 3) : ").strip()
    ext, mode_label = _compression_mode(mode)
    if ext is None:
        print("[Erreur] Choix invalide.")
        return 2

    output_filename = f"{folder_name}_Archive_{datetime.datetime.now():%Y%m%d_%H%M%S}{ext}"
    output_input = clean_input_path(cli_args.output) if cli_args and cli_args.output is not None else clean_input_path(
        input("Chemin de sortie (Entree = archive a cote du dossier source) : ")
    )
    try:
        output_path = resolve_archive_output_path(
            output_input, Path(target_folder).resolve().parent, output_filename, ext
        )
    except Exception as exc:
        print(f"[Erreur] Impossible de preparer le chemin de sortie : {exc}")
        return 2

    entries, removed_size = remove_output_from_entries(entries, output_path)
    total_size -= removed_size
    if removed_size:
        print("[Analyse] Une ancienne archive de sortie situee dans la source a ete exclue.")
    engine = getattr(cli_args, "engine", "auto")
    verify_mode = getattr(cli_args, "verify", "quick")
    try:
        backends = select_backend(mode, engine, tools)
    except RuntimeError as exc:
        print(f"[Erreur] {exc}")
        return 2

    print("\n" + "=" * 60)
    print(f"COMPRESSION {mode_label.upper()}")
    print("=" * 60)
    print(f"[Sortie] {output_path}")
    print(f"[Threads] {'auto' if requested_threads == 0 else requested_threads} (CPU logique : {effective_threads})")
    print(f"[Strategie] {' -> '.join(describe_backend(backend) for backend in backends)}")
    print(f"[Verification] {verify_mode}")
    global_start = time.perf_counter()
    try:
        compression_start = time.perf_counter()
        used_backend = execute_compression(
            mode, backends, entries, total_size, target_folder,
            output_path, tools, requested_threads, quiet=quiet,
        )
        compression_elapsed = time.perf_counter() - compression_start
        if not os.path.isfile(output_path):
            raise RuntimeError("Le moteur n'a produit aucun fichier d'archive.")
        verify_archive(output_path, mode, verify_mode, len(entries), tools, requested_threads)
        final_size = os.path.getsize(output_path)
        size_analysis = analyze_size_change(total_size, final_size)
        throughput = total_size / compression_elapsed if compression_elapsed > 0 else 0
        print("\n" + "=" * 60)
        print("COMPRESSION TERMINEE")
        print("=" * 60)
        print(f"Moteur             : {describe_backend(used_backend)}")
        print(f"Temps compression   : {compression_elapsed:.2f} s")
        print(f"Temps total         : {time.perf_counter() - global_start:.2f} s")
        print(f"Debit source        : {format_size(throughput)}/s")
        print(f"Taille source       : {format_size(total_size)}")
        print(f"Taille finale       : {format_size(final_size)}")
        label = "Gain d'espace" if size_analysis.variation <= 0 else "Augmentation"
        print(f"{label:<20}: {abs(size_analysis.reduction_percent):.2f}%")
        print(f"Fichiers            : {len(entries)}")
        print(f"Emplacement         : {output_path}")
        print("=" * 60)
        return 0
    except KeyboardInterrupt:
        safe_unlink(output_path)
        print("\n[Interruption] Operation annulee. Archive partielle supprimee.")
        return 130
    except Exception as exc:
        safe_unlink(output_path)
        print(f"\n[Erreur Fatale] {exc}")
        return 1


def build_parser():
    parser = argparse.ArgumentParser(
        description="SudMedia Folder Compressor - compression/decompression multithread"
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("-a", "--action", choices=["compress", "decompress"])
    actions.add_argument("-d", "--decompress", dest="action", action="store_const", const="decompress")
    parser.add_argument("-input", "--input", "--source", "-i")
    parser.add_argument("-mode", "--mode", "-m", choices=["1", "2", "3"])
    parser.add_argument("-output", "--output", "--destination", "-o")
    parser.add_argument("--threads", default="auto")
    parser.add_argument("--engine", choices=["auto", "external", "python"], default="auto")
    parser.add_argument("--verify", choices=["none", "quick", "full"], default="quick")
    parser.add_argument("--sevenzip")
    parser.add_argument("--xz")
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    action = args.action
    if action is None and args.input:
        action = "compress"
    elif action is None:
        print("\n1. Compresser un dossier")
        print("2. Decompresser une archive")
        action = {"1": "compress", "2": "decompress"}.get(
            input("\nVotre choix (1 ou 2) : ").strip()
        )
        if action is None:
            print("[Erreur] Choix invalide.")
            return 2
    return decompress_archive(args) if action == "decompress" else compress_folder(args)


if __name__ == "__main__":
    sys.exit(main())
