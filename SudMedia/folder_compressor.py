import argparse
import datetime
import lzma
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

# ============================================================
# SudMedia Folder Compressor - version optimisee
# ============================================================
# Objectifs :
# - utiliser automatiquement les moteurs natifs multithread disponibles ;
# - conserver un fallback 100 % Python ;
# - ne scanner le dossier qu'une seule fois ;
# - eviter les verifications couteuses par defaut ;
# - rester compatible Windows / Linux / macOS.
# ============================================================

EXCLUDE_PATTERNS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    ".vscode",
    ".idea",
    ".DS_Store",
    "Thumbs.db",
    "venv",
    ".next",
    "updraft",
}

XZ_MAGIC = b"\xfd7zXZ\x00"
BUFFER_SIZE = 1024 * 1024


@dataclass
class FileEntry:
    path: str
    arcname: str
    size: int


@dataclass
class Toolchain:
    sevenzip: str = None
    xz: str = None


class CompressionBackendError(RuntimeError):
    pass


class Progress:
    """Affichage limite pour ne pas ralentir les gros lots de petits fichiers."""

    def __init__(self, total_files, label="Compression", enabled=True):
        self.total_files = max(0, total_files)
        self.label = label
        self.enabled = enabled and self.total_files > 0
        self.current = 0
        self.last_percent = -1
        self.last_time = 0.0

    def update(self, increment=1, force=False):
        if not self.enabled:
            return

        self.current += increment
        percent = min(100.0, (self.current / self.total_files) * 100)
        now = time.monotonic()
        rounded = int(percent)

        # Au plus ~100 rafraichissements et pas plus de 5/s.
        if not force and rounded == self.last_percent and (now - self.last_time) < 0.20:
            return

        if not force and (now - self.last_time) < 0.08 and self.current < self.total_files:
            return

        self.last_percent = rounded
        self.last_time = now

        bar_length = 30
        filled = int(bar_length * min(self.current, self.total_files) / self.total_files)
        bar = "█" * filled + "░" * (bar_length - filled)
        print(
            f"\r[{self.label}] |{bar}| {percent:5.1f}% "
            f"({min(self.current, self.total_files)}/{self.total_files})",
            end="",
            flush=True,
        )

    def finish(self):
        if self.enabled:
            self.current = self.total_files
            self.update(0, force=True)
            print()


def format_size(size_in_bytes):
    value = float(size_in_bytes)
    for unit in ["O", "Ko", "Mo", "Go", "To"]:
        if value < 1024.0 or unit == "To":
            return f"{value:.2f} {unit}"
        value /= 1024.0


def clean_input_path(value):
    if value is None:
        return ""

    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value


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


def scan_folder(folder_path, quiet=False):
    """Un seul scan : taille + nombre + liste reutilisee pour la compression."""
    start = time.perf_counter()
    entries = []
    total_size = 0
    skipped = []

    for root, dirs, files in os.walk(folder_path, followlinks=False):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_PATTERNS]

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

    elapsed = time.perf_counter() - start
    if not quiet:
        print(f"[Analyse] Scan unique termine en {elapsed:.2f} s.")

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
    candidates = []
    if custom_path:
        candidates.append(custom_path)

    candidates.extend(["7zz", "7z", "7za"])

    if os.name == "nt":
        program_files = [
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        for base in program_files:
            if base:
                candidates.extend(
                    [
                        str(Path(base) / "7-Zip" / "7z.exe"),
                        str(Path(base) / "7-Zip" / "7zz.exe"),
                    ]
                )

    return find_executable(candidates)


def detect_xz(custom_path=None):
    candidates = []
    if custom_path:
        candidates.append(custom_path)

    candidates.append("xz")

    if os.name == "nt":
        for base in [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]:
            if base:
                # Git for Windows embarque souvent xz dans usr/bin.
                candidates.append(str(Path(base) / "Git" / "usr" / "bin" / "xz.exe"))

        candidates.extend(
            [
                r"C:\msys64\usr\bin\xz.exe",
                r"C:\msys32\usr\bin\xz.exe",
            ]
        )

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
        raise ValueError("--threads doit etre 'auto' ou un entier >= 1")

    if requested < 1:
        raise ValueError("--threads doit etre 'auto' ou un entier >= 1")

    return requested, requested


def thread_switch_7zip(requested_threads):
    return "-mmt=on" if requested_threads == 0 else f"-mmt={requested_threads}"


def thread_switch_xz(requested_threads):
    return "-T0" if requested_threads == 0 else f"-T{requested_threads}"


def safe_unlink(path):
    try:
        Path(path).unlink(missing_ok=True)
    except TypeError:
        # Python 3.7
        try:
            if Path(path).exists():
                Path(path).unlink()
        except OSError:
            pass
    except OSError:
        pass


def build_7zip_listfile(entries):
    fd, temp_path = tempfile.mkstemp(prefix="sudmedia_7z_", suffix=".txt")
    os.close(fd)

    try:
        with open(temp_path, "w", encoding="utf-8", newline="\n") as handle:
            for entry in entries:
                if "\n" in entry.arcname or "\r" in entry.arcname:
                    raise CompressionBackendError(
                        "7-Zip via listfile ne peut pas traiter de facon fiable un nom contenant un retour ligne."
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
        if len(error) > 2000:
            error = error[-2000:]
        raise CompressionBackendError(
            f"Commande externe echouee (code {process.returncode})"
            + (f" : {error}" if error else "")
        )


def compress_zip_7zip(entries, target_folder, output_path, mode, sevenzip, requested_threads):
    listfile = build_7zip_listfile(entries)
    safe_unlink(output_path)

    try:
        if mode == "1":
            # Priorite vitesse.
            method_args = ["-mm=Deflate", "-mx=1"]
        else:
            # BZip2 conserve le positionnement du mode MEDIUM, avec MT natif.
            method_args = ["-mm=BZip2", "-mx=7"]

        command = [
            sevenzip,
            "a",
            "-tzip",
            str(output_path),
            f"@{listfile}",
            "-scsUTF-8",
            "-y",
            "-bd",
            "-bb0",
            "-bso0",
            "-bsp0",
            thread_switch_7zip(requested_threads),
            *method_args,
        ]
        run_command(command, cwd=target_folder)
    finally:
        safe_unlink(listfile)


def compress_zip_python(entries, output_path, mode, quiet=False):
    if mode == "1":
        compression = zipfile.ZIP_DEFLATED
        # Niveau 1 : forte reduction CPU pour le mode RAPIDE.
        level = 1
    else:
        compression = zipfile.ZIP_BZIP2
        # Compromis taille / temps au lieu du niveau 9 systematique.
        level = 7

    safe_unlink(output_path)
    progress = Progress(len(entries), enabled=not quiet)

    with zipfile.ZipFile(output_path, "w", compression=compression, compresslevel=level, allowZip64=True) as archive:
        for entry in entries:
            archive.write(entry.path, entry.arcname)
            progress.update()

    progress.finish()


def stream_tar_to_process(entries, process, quiet=False):
    progress = Progress(len(entries), enabled=not quiet)

    try:
        with tarfile.open(fileobj=process.stdin, mode="w|", format=tarfile.PAX_FORMAT) as tar:
            for entry in entries:
                tar.add(entry.path, arcname=entry.arcname, recursive=False)
                progress.update()

        process.stdin.close()
        process.stdin = None
        stderr = process.stderr.read() if process.stderr else ""
        return_code = process.wait()
        progress.finish()

        if return_code != 0:
            raise CompressionBackendError(
                f"Compresseur externe echoue (code {return_code})"
                + (f" : {stderr.strip()[-2000:]}" if stderr and stderr.strip() else "")
            )

    except Exception:
        try:
            if process.stdin:
                process.stdin.close()
        except Exception:
            pass

        if process.poll() is None:
            process.kill()
        process.wait()
        raise


def compress_tar_xz_external_xz(entries, output_path, xz_path, requested_threads, quiet=False):
    safe_unlink(output_path)
    env = os.environ.copy()
    # Evite qu'un XZ_DEFAULTS local surcharge silencieusement nos reglages.
    env.pop("XZ_DEFAULTS", None)

    command = [
        xz_path,
        "-c",
        "-6",
        thread_switch_xz(requested_threads),
    ]

    with open(output_path, "wb", buffering=BUFFER_SIZE) as output_handle:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=output_handle,
            stderr=subprocess.PIPE,
            env=env,
        )
        stream_tar_to_process(entries, process, quiet=quiet)


def compress_tar_xz_external_7zip(entries, output_path, sevenzip, requested_threads, quiet=False):
    """Fallback multithread Windows : TAR Python streame vers le compresseur XZ de 7-Zip."""
    safe_unlink(output_path)

    command = [
        sevenzip,
        "a",
        "-txz",
        str(output_path),
        "-si",
        "-y",
        "-bd",
        "-bb0",
        "-bso0",
        "-bsp0",
        "-mx=6",
        thread_switch_7zip(requested_threads),
    ]

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    stream_tar_to_process(entries, process, quiet=quiet)


def compress_tar_xz_python(entries, output_path, quiet=False):
    safe_unlink(output_path)
    progress = Progress(len(entries), enabled=not quiet)

    with tarfile.open(output_path, "w:xz", preset=6, format=tarfile.PAX_FORMAT) as tar:
        for entry in entries:
            tar.add(entry.path, arcname=entry.arcname, recursive=False)
            progress.update()

    progress.finish()


def quick_verify_zip(output_path, expected_count):
    with zipfile.ZipFile(output_path, "r", allowZip64=True) as archive:
        count = sum(1 for item in archive.infolist() if not item.is_dir())
        if count != expected_count:
            raise RuntimeError(f"ZIP incomplet : {count} fichier(s) dans l'archive, {expected_count} attendu(s).")


def full_verify_zip(output_path, expected_count):
    with zipfile.ZipFile(output_path, "r", allowZip64=True) as archive:
        count = sum(1 for item in archive.infolist() if not item.is_dir())
        if count != expected_count:
            raise RuntimeError(f"ZIP incomplet : {count} fichier(s) dans l'archive, {expected_count} attendu(s).")
        bad_file = archive.testzip()
        if bad_file:
            raise RuntimeError(f"Archive ZIP corrompue au fichier : {bad_file}")


def quick_verify_xz(output_path):
    if os.path.getsize(output_path) < len(XZ_MAGIC):
        raise RuntimeError("Archive TAR.XZ vide ou tronquee.")

    with open(output_path, "rb") as handle:
        if handle.read(len(XZ_MAGIC)) != XZ_MAGIC:
            raise RuntimeError("Signature XZ invalide.")

    # Decode seulement le debut du flux : verification structurelle rapide.
    with lzma.open(output_path, "rb") as handle:
        handle.read(1024)


def full_verify_xz(output_path, xz_path=None, requested_threads=0):
    if xz_path:
        env = os.environ.copy()
        env.pop("XZ_DEFAULTS", None)
        run_command(
            [xz_path, "-t", thread_switch_xz(requested_threads), str(output_path)],
            env=env,
        )
        return

    # Fallback Python : lecture/decompression complete jusqu'a EOF.
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
        if verify_mode == "quick":
            quick_verify_zip(output_path, expected_count)
        else:
            full_verify_zip(output_path, expected_count)
    else:
        if verify_mode == "quick":
            quick_verify_xz(output_path)
        else:
            full_verify_xz(output_path, xz_path=tools.xz, requested_threads=requested_threads)

    print(f"[Verification] OK en {time.perf_counter() - start:.2f} s.")


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
            raise RuntimeError("Aucun moteur externe compatible detecte.")
        return external

    # auto : meilleur moteur d'abord, puis fallback Python.
    return external + ["python"]


def describe_backend(backend):
    return {
        "7zip": "7-Zip natif multithread",
        "xz": "XZ natif multithread + TAR streame",
        "7zip-xz": "7-Zip/XZ multithread + TAR streame",
        "python": "Python standard (fallback)",
    }.get(backend, backend)


def execute_compression(mode, backends, entries, target_folder, output_path, tools, requested_threads, quiet=False):
    errors = []

    for index, backend in enumerate(backends):
        try:
            print(f"[Moteur] {describe_backend(backend)}")

            if backend == "7zip":
                compress_zip_7zip(
                    entries,
                    target_folder,
                    output_path,
                    mode,
                    tools.sevenzip,
                    requested_threads,
                )
            elif backend == "xz":
                compress_tar_xz_external_xz(
                    entries,
                    output_path,
                    tools.xz,
                    requested_threads,
                    quiet=quiet,
                )
            elif backend == "7zip-xz":
                compress_tar_xz_external_7zip(
                    entries,
                    output_path,
                    tools.sevenzip,
                    requested_threads,
                    quiet=quiet,
                )
            elif backend == "python":
                if mode in {"1", "2"}:
                    compress_zip_python(entries, output_path, mode, quiet=quiet)
                else:
                    compress_tar_xz_python(entries, output_path, quiet=quiet)
            else:
                raise RuntimeError(f"Backend inconnu : {backend}")

            return backend

        except Exception as exc:
            errors.append((backend, exc))
            safe_unlink(output_path)

            if index < len(backends) - 1:
                print(f"[Moteur] Echec de {describe_backend(backend)} : {exc}")
                print(f"[Moteur] Bascule automatique vers {describe_backend(backends[index + 1])}...")
                continue
            raise

    raise RuntimeError("Aucun backend disponible.")


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


def compress_folder(cli_args=None):
    print(
        r"""
 ____            _    _             _     _
/ ___| _   _  __| |  / \   _ __ ___| |__ (_)_   _____
\___ \| | | |/ _` | / _ \ | '__/ __| '_ \| \ \ / / _ \
 ___) | |_| | (_| |/ ___ \| | | (__| | | | |\ V /  __/
|____/ \__,_|\__,_/_/   \_\_|  \___|_| |_|_| \_/ \___|

        FOLDER COMPRESSOR - FAST ENGINE
    """
    )

    quiet = bool(getattr(cli_args, "quiet", False))

    if cli_args and cli_args.input:
        target_folder = clean_input_path(cli_args.input)
    else:
        target_folder = clean_input_path(input("📂 Dossier a compresser (glissez-deposez ou nom) : "))

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
    file_count = len(entries)

    print(f"[Analyse] Taille a traiter : {format_size(total_size)} ({file_count} fichiers)")
    print(f"[Analyse] CPU : {max(1, os.cpu_count() or 1)} thread(s) logique(s)")
    print(
        "[Detection] 7-Zip: "
        + (tools.sevenzip if tools.sevenzip else "absent -> fallback Python pour ZIP")
    )
    print(
        "[Detection] XZ: "
        + (tools.xz if tools.xz else "absent -> 7-Zip XZ ou fallback Python pour TAR.XZ")
    )

    if skipped:
        print(f"[Attention] {len(skipped)} fichier(s) impossible(s) a analyser et ignores.")
        for path, error in skipped[:5]:
            print(f"  - {path}: {error}")
        if len(skipped) > 5:
            print(f"  ... et {len(skipped) - 5} autre(s).")

    if cli_args and cli_args.mode:
        mode = cli_args.mode
    else:
        print("\n" + "=" * 60)
        print("MODES DE COMPRESSION")
        print("=" * 60)
        print("1. CLASSIQUE - ZIP Deflate, priorite vitesse")
        print("2. MEDIUM    - ZIP BZip2, meilleur gain d'espace")
        print("3. ULTRA     - TAR.XZ / LZMA2, multithread si possible")
        mode = input("\nVotre choix (1, 2 ou 3) : ").strip()

    if mode not in {"1", "2", "3"}:
        print("[Erreur] Choix invalide.")
        return 2

    if mode == "1":
        ext = ".zip"
        mode_label = "Classique"
    elif mode == "2":
        ext = ".zip"
        mode_label = "Medium"
    else:
        ext = ".tar.xz"
        mode_label = "Ultra"

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{folder_name}_Archive_{timestamp}{ext}"

    if cli_args and cli_args.output is not None:
        output_input = clean_input_path(cli_args.output)
    else:
        print("\n" + "=" * 60)
        print("SORTIE DE L'ARCHIVE")
        print("=" * 60)
        output_input = clean_input_path(
            input(
                "Chemin de sortie, absolu ou relatif "
                "(Entree = archive a cote du dossier source) : "
            )
        )

    default_output_dir = Path(target_folder).resolve().parent

    try:
        output_path = resolve_archive_output_path(
            output_input=output_input,
            default_output_dir=default_output_dir,
            default_filename=output_filename,
            expected_ext=ext,
        )
    except Exception as exc:
        print(f"[Erreur] Impossible de preparer le chemin de sortie : {exc}")
        return 2

    entries, removed_size = remove_output_from_entries(entries, output_path)
    if removed_size:
        total_size -= removed_size
        file_count = len(entries)
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
    print(f"[Strategie] {' -> '.join(describe_backend(b) for b in backends)}")
    print(f"[Verification] {verify_mode}")

    global_start = time.perf_counter()

    try:
        compression_start = time.perf_counter()
        used_backend = execute_compression(
            mode,
            backends,
            entries,
            target_folder,
            output_path,
            tools,
            requested_threads,
            quiet=quiet,
        )
        compression_elapsed = time.perf_counter() - compression_start

        if not os.path.isfile(output_path):
            raise RuntimeError("Le moteur n'a produit aucun fichier d'archive.")

        verify_archive(
            output_path,
            mode,
            verify_mode,
            len(entries),
            tools,
            requested_threads,
        )

        total_elapsed = time.perf_counter() - global_start
        final_size = os.path.getsize(output_path)
        reduction = (1 - (final_size / total_size)) * 100 if total_size > 0 else 0.0
        throughput = total_size / compression_elapsed if compression_elapsed > 0 else 0

        print("\n" + "=" * 60)
        print("COMPRESSION TERMINEE")
        print("=" * 60)
        print(f"Moteur             : {describe_backend(used_backend)}")
        print(f"Temps compression   : {compression_elapsed:.2f} s")
        print(f"Temps total         : {total_elapsed:.2f} s")
        print(f"Debit source        : {format_size(throughput)}/s")
        print(f"Taille source       : {format_size(total_size)}")
        print(f"Taille finale       : {format_size(final_size)}")
        print(f"Gain d'espace       : {reduction:.2f}%")
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
        description="SudMedia Folder Compressor - version optimisee multithread"
    )
    parser.add_argument("-input", "--input", "-i", help="Dossier a compresser")
    parser.add_argument(
        "-mode",
        "--mode",
        "-m",
        choices=["1", "2", "3"],
        help="Mode : 1=ZIP rapide, 2=ZIP BZip2, 3=TAR.XZ",
    )
    parser.add_argument("-output", "--output", "-o", help="Chemin de sortie de l'archive")
    parser.add_argument(
        "--threads",
        default="auto",
        help="Nombre de threads ou 'auto' (defaut : auto)",
    )
    parser.add_argument(
        "--engine",
        choices=["auto", "external", "python"],
        default="auto",
        help="Moteur : auto (defaut), external, python",
    )
    parser.add_argument(
        "--verify",
        choices=["none", "quick", "full"],
        default="quick",
        help="Verification : none=max vitesse, quick=structure, full=lecture complete",
    )
    parser.add_argument("--sevenzip", help="Chemin force vers 7z/7zz/7za")
    parser.add_argument("--xz", help="Chemin force vers xz")
    parser.add_argument(
        "--diagnostic",
        action="store_true",
        help="Affiche les moteurs et CPU detectes",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduit l'affichage et desactive la barre de progression Python",
    )
    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(compress_folder(args))
