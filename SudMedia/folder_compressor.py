"""CLI du compresseur de dossiers SudMedia.

La logique réutilisable est répartie dans ``SudMedia.utils.folder_archive``. Les imports
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

import zipfile

from SudMedia.utils.folder_archive import (
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
from SudMedia.utils.folder_archive.compression import (
    add_entries_to_tar,
    copy_with_progress,
    stream_tar_to_process,
)
from SudMedia.utils.folder_archive.extraction import inspect_zip_for_extraction
from SudMedia.utils.folder_archive.toolchain import (
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
    find_archive_files,
    make_staging_folder,
    remove_output_from_entries,
    resolve_archive_output_path,
    resolve_extraction_paths,
    safe_member_path,
    scan_folder,
    unique_path,
)
from SudMedia.utils.hashing import content_hash, file_crc32
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


def check_archive_already_extracted(
    archive_path: Path, destination_folder: Path
) -> tuple[bool, int, int]:
    """Vérifie si tous les fichiers de l'archive sont déjà présents avec un CRC32 identique."""
    if not destination_folder.exists() or not destination_folder.is_dir():
        return False, 0, 0
    try:
        format_name = detect_archive_format(archive_path)
        if format_name == "zip":
            with zipfile.ZipFile(archive_path, "r", allowZip64=True) as archive:
                infolist = [info for info in archive.infolist() if not info.is_dir()]
                if not infolist:
                    return False, 0, 0
                total_size = 0
                for info in infolist:
                    target = safe_member_path(destination_folder, info.filename)
                    if not target.is_file():
                        return False, 0, 0
                    if target.stat().st_size != info.file_size:
                        return False, 0, 0
                    if file_crc32(target) != info.CRC:
                        return False, 0, 0
                    total_size += info.file_size
                return True, len(infolist), total_size
    except Exception:
        return False, 0, 0
    return False, 0, 0


def smart_merge_extracted(
    staging_folder: Path,
    destination_folder: Path,
) -> tuple[int, int, int, int]:
    """Fusionne le dossier d'étape vers la destination en vérifiant les sommes de contrôle.

    - Si le fichier n'existe pas : extrait normalement.
    - Si le fichier existe avec le même checksum (SHA256) : ignoré (économie de puissance et pas de doublon).
    - Si le fichier existe avec un checksum différent : renommé avec un index unique pour préserver les deux.
    """
    new_count = 0
    skipped_count = 0
    renamed_count = 0
    total_extracted_size = 0

    destination_folder.mkdir(parents=True, exist_ok=True)

    for root, _, filenames in os.walk(staging_folder):
        for filename in filenames:
            staged_file = Path(root) / filename
            rel_path = staged_file.relative_to(staging_folder)
            target_file = destination_folder / rel_path

            if not target_file.exists():
                target_file.parent.mkdir(parents=True, exist_ok=True)
                file_size = staged_file.stat().st_size
                shutil.move(str(staged_file), str(target_file))
                new_count += 1
                total_extracted_size += file_size
            else:
                staged_size = staged_file.stat().st_size
                target_size = target_file.stat().st_size
                is_identical = False
                if staged_size == target_size:
                    if content_hash(staged_file) == content_hash(target_file):
                        is_identical = True

                if is_identical:
                    skipped_count += 1
                else:
                    renamed_target = unique_path(target_file)
                    renamed_target.parent.mkdir(parents=True, exist_ok=True)
                    file_size = staged_file.stat().st_size
                    shutil.move(str(staged_file), str(renamed_target))
                    renamed_count += 1
                    total_extracted_size += file_size

    shutil.rmtree(staging_folder, ignore_errors=True)
    return new_count, skipped_count, renamed_count, total_extracted_size


def decompress_single_archive(
    archive_path: Path,
    destination_input: str | None = None,
    tools: Toolchain | None = None,
    cli_args=None,
    create_subfolder: bool = True,
    quiet: bool = False,
    show_header: bool = True,
    show_footer: bool = True,
) -> tuple[str, int | None, int | None, Path]:
    """Décompresse une archive individuelle vers sa destination."""
    archive_format = detect_archive_format(archive_path)
    requested_threads, effective_threads = parse_threads(
        getattr(cli_args, "threads", "auto")
    )
    if tools is None:
        tools = detect_toolchain(cli_args)

    destination_root, final_folder = resolve_extraction_paths(
        archive_path, destination_input, create_subfolder=create_subfolder
    )

    # Vérification préventive : l'archive est-elle déjà 100% extraite et identique ?
    is_identical, total_files, total_sz = check_archive_already_extracted(
        archive_path, final_folder
    )
    if is_identical:
        if show_header and not quiet:
            print("\n" + "=" * 60)
            print("DECOMPRESSION")
            print("=" * 60)
            print(f"[Source] {archive_path}")
            print(f"[Destination] {final_folder}")
            print(f"[Format] {archive_format.upper()}")
        if show_footer and not quiet:
            print("\n" + "=" * 60)
            print("DECOMPRESSION TERMINEE")
            print("=" * 60)
            print("Statut             : Deja extrait (100% identique, checksum valide)")
            print(f"Fichiers ignores    : {total_files} (aucun doublon cree)")
            print(f"Emplacement         : {final_folder}")
            print("=" * 60)
        return "skip-identical", total_files, 0, final_folder

    staging_folder = make_staging_folder(
        destination_root, final_folder, allow_existing_final=True
    )

    if show_header and not quiet:
        print("\n" + "=" * 60)
        print("DECOMPRESSION")
        print("=" * 60)
        print(f"[Source] {archive_path}")
        print(f"[Destination] {final_folder}")
        print(f"[Format] {archive_format.upper()}")
        print(
            f"[Threads] {'auto' if requested_threads == 0 else requested_threads} (CPU logique : {effective_threads})"
        )

    started_at = time.perf_counter()
    try:
        used_backend, _raw_files, _raw_size = execute_extraction(
            archive_format,
            archive_path,
            staging_folder,
            tools,
            getattr(cli_args, "engine", "auto"),
            requested_threads,
            effective_threads,
            quiet=quiet,
        )
        new_cnt, skipped_cnt, renamed_cnt, extracted_sz = smart_merge_extracted(
            staging_folder, final_folder
        )
        elapsed = time.perf_counter() - started_at

        if show_footer and not quiet:
            print("\n" + "=" * 60)
            print("DECOMPRESSION TERMINEE")
            print("=" * 60)
            print(f"Moteur             : {describe_backend(used_backend)}")
            print(f"Temps total         : {elapsed:.2f} s")
            print(f"Nouveaux fichiers   : {new_cnt}")
            if skipped_cnt:
                print(f"Fichiers identiques : {skipped_cnt} (non dupliques)")
            if renamed_cnt:
                print(f"Fichiers renomes    : {renamed_cnt} (conflits evites)")
            print(f"Taille extraite     : {format_size(extracted_sz)}")
            print(f"Emplacement         : {final_folder}")
            print("=" * 60)
        return used_backend, new_cnt + renamed_cnt, extracted_sz, final_folder
    except Exception:
        shutil.rmtree(staging_folder, ignore_errors=True)
        raise


def decompress_folder_archives(
    target_folder: Path,
    archives: list[Path],
    destination_input: str | None = None,
    tools: Toolchain | None = None,
    cli_args=None,
    create_subfolder: bool = True,
    quiet: bool = False,
) -> int:
    """Décompresse toutes les archives d'un dossier par lot."""
    requested_threads, effective_threads = parse_threads(
        getattr(cli_args, "threads", "auto")
    )
    if tools is None:
        tools = detect_toolchain(cli_args)

    if destination_input:
        dest_root = Path(destination_input).expanduser()
        if not dest_root.is_absolute():
            dest_root = Path.cwd() / dest_root
    else:
        dest_root = target_folder

    dest_root = dest_root.resolve()
    dest_root.mkdir(parents=True, exist_ok=True)

    if not quiet:
        print("\n" + "=" * 60)
        print("DECOMPRESSION PAR LOT")
        print("=" * 60)
        print(f"[Dossier source] {target_folder}")
        print(f"[Archives trouvees] {len(archives)}")
        print(f"[Destination] {dest_root}")
        print(
            f"[Organisation] {'Sous-dossier dedie par archive' if create_subfolder else 'Directement dans la destination'}"
        )
        print(
            f"[Threads] {'auto' if requested_threads == 0 else requested_threads} (CPU logique : {effective_threads})"
        )
        print("=" * 60)

    total_extracted_size = 0
    total_files_count = 0
    successes = []
    failures = []
    batch_start = time.perf_counter()

    for idx, archive_path in enumerate(archives, start=1):
        if not quiet:
            print(f"\n[{idx}/{len(archives)}] Archive : {archive_path.name}")
        arch_start = time.perf_counter()
        try:
            used_backend, file_count, total_size, final_folder = (
                decompress_single_archive(
                    archive_path,
                    destination_input=str(dest_root),
                    tools=tools,
                    cli_args=cli_args,
                    create_subfolder=create_subfolder,
                    quiet=quiet,
                    show_header=False,
                    show_footer=False,
                )
            )
            arch_elapsed = time.perf_counter() - arch_start
            if total_size is not None:
                total_extracted_size += total_size
            if file_count is not None:
                total_files_count += file_count
            successes.append(
                (archive_path, final_folder, arch_elapsed, total_size, used_backend)
            )
            if not quiet:
                if used_backend == "skip-identical":
                    print(
                        f"  -> Deja extrait (100% identique, decompresssion ignoree) -> {final_folder}"
                    )
                else:
                    size_label = (
                        f" ({format_size(total_size)})" if total_size is not None else ""
                    )
                    print(
                        f"  -> Reussie en {arch_elapsed:.2f} s{size_label} -> {final_folder}"
                    )
        except KeyboardInterrupt:
            if not quiet:
                print(
                    f"\n[Interruption] Operation annulee par l'utilisateur pendant '{archive_path.name}'."
                )
            return 130
        except Exception as exc:
            failures.append((archive_path, str(exc)))
            if not quiet:
                print(f"  -> Echec : {exc}")

    total_batch_time = time.perf_counter() - batch_start
    if not quiet:
        print("\n" + "=" * 60)
        print("BILAN DE LA DECOMPRESSION PAR LOT")
        print("=" * 60)
        print(f"Archives traitees   : {len(archives)}")
        print(f"Succes              : {len(successes)}")
        print(f"Echecs              : {len(failures)}")
        print(f"Fichiers extraits   : {total_files_count}")
        print(f"Taille totale       : {format_size(total_extracted_size)}")
        print(f"Temps total         : {total_batch_time:.2f} s")
        print(f"Dossier destination : {dest_root}")
        if failures:
            print("\nDetails des echecs :")
            for arch, err in failures:
                print(f"  - {arch.name} : {err}")
        print("=" * 60)
    return 0 if not failures else 1


def decompress_archive(cli_args=None):
    configure_console_output()
    quiet = bool(getattr(cli_args, "quiet", False))
    raw_input = (
        cli_args.input
        if cli_args and cli_args.input
        else input(
            "📦 Archive ou dossier d'archives a decompresser (.zip, .tar.xz ou dossier) : "
        )
    )
    input_path = _resolved_input_path(raw_input)
    if not input_path.exists():
        print(f"[Erreur] '{input_path}' n'existe pas.")
        return 2

    requested_threads, effective_threads = parse_threads(
        getattr(cli_args, "threads", "auto")
    )
    tools = detect_toolchain(cli_args)
    if getattr(cli_args, "diagnostic", False):
        print_diagnostics(tools, requested_threads, effective_threads)

    # Cas 1 : Dossier d'archives
    if input_path.is_dir():
        recursive = getattr(cli_args, "recursive", False)
        archives = find_archive_files(input_path, recursive=recursive)
        if not archives and not recursive and not (cli_args and cli_args.input):
            sub_choice = (
                input(
                    "Aucune archive au 1er niveau. Rechercher recursivement dans les sous-dossiers ? (o/N) : "
                )
                .strip()
                .lower()
            )
            if sub_choice in {"o", "oui", "y", "yes"}:
                archives = find_archive_files(input_path, recursive=True)

        if not archives:
            if not quiet:
                print(
                    f"[Info] Aucune archive (.zip, .tar.xz, .txz) trouvee dans '{input_path}'."
                )
            return 0

        if not quiet:
            print(
                f"[Analyse] {len(archives)} archive(s) detectee(s) dans le dossier."
            )
        if cli_args and cli_args.output is not None:
            destination_input = clean_input_path(cli_args.output)
        else:
            destination_input = clean_input_path(
                input(
                    "Dossier parent de destination (Entree = dans le dossier des archives) : "
                )
            )

        if getattr(cli_args, "no_subfolder", False):
            create_subfolder = False
        elif not (cli_args and cli_args.input):
            subfolder_choice = (
                input(
                    "Creer un sous-dossier pour chaque archive ? (O/n, defaut = O) : "
                )
                .strip()
                .lower()
            )
            create_subfolder = subfolder_choice not in {"n", "non", "no"}
        else:
            create_subfolder = True

        return decompress_folder_archives(
            input_path,
            archives,
            destination_input=destination_input,
            tools=tools,
            cli_args=cli_args,
            create_subfolder=create_subfolder,
            quiet=quiet,
        )

    # Cas 2 : Fichier archive unique
    try:
        detect_archive_format(input_path)
    except ValueError as exc:
        print(f"[Erreur] {exc}")
        return 2

    if cli_args and cli_args.output is not None:
        destination_input = clean_input_path(cli_args.output)
    else:
        destination_input = clean_input_path(
            input(
                "Dossier parent de destination (Entree = a cote de l'archive) : "
            )
        )

    create_subfolder = not getattr(cli_args, "no_subfolder", False)
    try:
        decompress_single_archive(
            input_path,
            destination_input=destination_input,
            tools=tools,
            cli_args=cli_args,
            create_subfolder=create_subfolder,
            quiet=quiet,
            show_header=True,
            show_footer=True,
        )
        return 0
    except KeyboardInterrupt:
        print(
            "\n[Interruption] Operation annulee. Extraction partielle supprimee."
        )
        return 130
    except Exception as exc:
        print(f"\n[Erreur Fatale] {exc}")
        return 1


def _compression_mode(mode):
    return {"1": (".zip", "Classique"), "2": (".zip", "Medium"), "3": (".tar.xz", "Ultra")}.get(
        mode, (None, None)
    )


def _split_exclusion_values(values):
    """Normalise les options d'exclusion repetables et separees par virgules."""
    normalized = []
    for raw_value in values or []:
        for value in str(raw_value).replace(";", ",").split(","):
            clean_value = value.strip().strip("\"'")
            if clean_value:
                normalized.append(clean_value)
    return normalized


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
    exclude_folders = _split_exclusion_values(getattr(cli_args, "exclude_folder", []))
    exclude_files = _split_exclusion_values(getattr(cli_args, "exclude_file", []))
    exclude_extensions = _split_exclusion_values(getattr(cli_args, "exclude_extension", []))
    entries, total_size, skipped = scan_folder(
        target_folder,
        quiet=quiet,
        exclude_folders=exclude_folders,
        exclude_files=exclude_files,
        exclude_extensions=exclude_extensions,
    )
    print(f"[Analyse] Taille a traiter : {format_size(total_size)} ({len(entries)} fichiers)")
    if exclude_folders or exclude_files or exclude_extensions:
        print("[Analyse] Exclusions personnalisees appliquees :")
        if exclude_folders:
            print(f"  - Dossiers : {', '.join(exclude_folders)}")
        if exclude_files:
            print(f"  - Fichiers : {', '.join(exclude_files)}")
        if exclude_extensions:
            print(f"  - Extensions : {', '.join(exclude_extensions)}")
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
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Rechercher les archives recursivement dans les sous-dossiers.",
    )
    parser.add_argument(
        "--no-subfolder",
        "--flat",
        action="store_true",
        help="Extraire directement dans la destination sans creer de sous-dossier par archive.",
    )
    parser.add_argument("--threads", default="auto")
    parser.add_argument("--engine", choices=["auto", "external", "python"], default="auto")
    parser.add_argument("--verify", choices=["none", "quick", "full"], default="quick")
    parser.add_argument("--sevenzip")
    parser.add_argument("--xz")
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--exclude-folder",
        "--exclude-dir",
        action="append",
        default=[],
        help="Dossier a exclure de l'archive, par nom ou chemin relatif. Repetable, virgules acceptees.",
    )
    parser.add_argument(
        "--exclude-file",
        action="append",
        default=[],
        help="Fichier a exclure de l'archive, par nom ou chemin relatif. Repetable, virgules acceptees.",
    )
    parser.add_argument(
        "--exclude-extension",
        "--exclude-ext",
        action="append",
        default=[],
        help="Extension a exclure de l'archive, avec ou sans point. Repetable, virgules acceptees.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    action = args.action
    if action is None and args.input:
        input_path = _resolved_input_path(args.input)
        if input_path.is_file():
            try:
                detect_archive_format(input_path)
                action = "decompress"
            except ValueError:
                action = "compress"
        else:
            action = "compress"
    elif action is None:
        print("\n1. Compresser un dossier")
        print("2. Decompresser une archive ou un dossier d'archives")
        action = {"1": "compress", "2": "decompress"}.get(
            input("\nVotre choix (1 ou 2) : ").strip()
        )
        if action is None:
            print("[Erreur] Choix invalide.")
            return 2
    return decompress_archive(args) if action == "decompress" else compress_folder(args)


if __name__ == "__main__":
    sys.exit(main())
