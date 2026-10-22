import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from pathlib import Path


def get_emojis(use_utf8=True):
    return {
        "BYE": "👋" if use_utf8 else "[BYE]",
        "CHART": "📊" if use_utf8 else "[STATS]",
        "COPY": "📄" if use_utf8 else "[COPY]",
        "DOOR": "🚪" if use_utf8 else "[EXIT]",
        "ERROR": "❌" if use_utf8 else "[ERROR]",
        "FOLDER": "📂" if use_utf8 else "[DIR]",
        "GEAR": "⚙️" if use_utf8 else "[CFG]",
        "HOURGLASS": "⏳" if use_utf8 else "[WAIT]",
        "POINTER": "👉" if use_utf8 else ">",
        "ROCKET": "🚀" if use_utf8 else "[START]",
        "SEARCH": "🔍" if use_utf8 else "[SCAN]",
        "SUCCESS": "✅" if use_utf8 else "[OK]",
        "SYNC": "🔄" if use_utf8 else "[SYNC]",
        "TEST": "🧪" if use_utf8 else "[TEST]",
        "WARN": "⚠️" if use_utf8 else "[WARN]",
    }


_UTF8_SYSTEM = (getattr(sys.stdout, "encoding", "") or "").lower() == "utf-8"
E = get_emojis(_UTF8_SYSTEM)
SCRIPT_DIR = Path(__file__).resolve().parent
STATE_DIR = SCRIPT_DIR / ".sud_folder_sync_state"
DEFAULT_TRASH_RETENTION_DAYS = 30


DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
    ".sud_folder_sync_state",
}


@dataclass(frozen=True)
class FileInfo:
    relative_path: Path
    absolute_path: Path
    size: int
    created_ns: int
    modified_ns: int

    @property
    def sync_key(self):
        return (self.created_ns, self.modified_ns, self.size)


@dataclass
class SyncStats:
    copied_left_to_right: int = 0
    copied_right_to_left: int = 0
    deleted_left: int = 0
    deleted_right: int = 0
    unchanged: int = 0
    conflicts: int = 0
    errors: int = 0

    @property
    def changes(self):
        return (
            self.copied_left_to_right
            + self.copied_right_to_left
            + self.deleted_left
            + self.deleted_right
        )


def safe_print(msg="", end="\n"):
    try:
        print(msg, end=end, flush=True)
    except UnicodeEncodeError:
        clean_msg = str(msg).encode("ascii", "ignore").decode("ascii")
        print(clean_msg, end=end, flush=True)


class CompactRenderer:
    def __init__(self):
        self.line_length = 0
        self.width = shutil.get_terminal_size((100, 24)).columns

    def render(self, line):
        width = shutil.get_terminal_size((self.width, 24)).columns
        self.width = max(20, width)
        clean_line = line.replace("\n", " ")
        visible = clean_line[: self.width - 1]
        padding = max(0, self.line_length - len(visible))
        safe_print("\r" + visible + (" " * padding), end="")
        self.line_length = len(visible)

    def close(self):
        if self.line_length:
            safe_print("")


def add_stats(total, current):
    total.copied_left_to_right += current.copied_left_to_right
    total.copied_right_to_left += current.copied_right_to_left
    total.deleted_left += current.deleted_left
    total.deleted_right += current.deleted_right
    total.unchanged += current.unchanged
    total.conflicts += current.conflicts
    total.errors += current.errors


def afficher_en_tete():
    safe_print(
        r"""
 ____            _ _____     _     _            ____                  
/ ___| _   _  __| |  ___|__ | | __| | ___ _ __ / ___| _   _ _ __   ___ 
\___ \| | | |/ _` | |_ / _ \| |/ _` |/ _ \ '__|\___ \| | | | '_ \ / __|
 ___) | |_| | (_| |  _| (_) | | (_| |  __/ |    ___) | |_| | | | | (__ 
|____/ \__,_|\__,_|_|  \___/|_|\__,_|\___|_|   |____/ \__, |_| |_|\___|
                                                       |___/            
    """
    )


def format_duration(seconds):
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, sec = divmod(int(seconds), 60)
    return f"{minutes}m{sec:02d}s"


def normalize_root(path_text):
    return Path(path_text.strip().strip('"')).expanduser().resolve()


def should_skip_dir(dir_name, excluded_dirs):
    return dir_name in excluded_dirs


def scan_folder(root, excluded_dirs):
    files = {}
    def scan_error(exc):
        raise exc

    for current_root, dirnames, filenames in os.walk(root, onerror=scan_error):
        dirnames[:] = [
            d for d in dirnames if not should_skip_dir(d, excluded_dirs)
        ]
        current_path = Path(current_root)
        for filename in filenames:
            absolute_path = current_path / filename
            stat = absolute_path.stat()

            relative_path = absolute_path.relative_to(root)
            files[relative_path] = FileInfo(
                relative_path=relative_path,
                absolute_path=absolute_path,
                size=stat.st_size,
                created_ns=stat.st_ctime_ns,
                modified_ns=stat.st_mtime_ns,
            )
    return files


def ensure_root_available(root):
    if not root.is_dir():
        raise OSError(f"Dossier inaccessible pendant la synchronisation : {root}")


def deletion_plan(left_files, right_files, previous_state):
    planned = []
    for relative_path in sorted(set(left_files) ^ set(right_files), key=lambda p: str(p).lower()):
        if str(relative_path) not in previous_state:
            continue
        if relative_path in left_files:
            planned.append(("left", left_files[relative_path]))
        else:
            planned.append(("right", right_files[relative_path]))
    return planned


def write_deletion_manifest(left_root, right_root, planned, dry_run):
    if not planned:
        return None, None
    run_id = datetime.now().strftime("%Y-%m-%d-%H-%M-%S") + "-" + uuid.uuid4().hex[:8]
    pair_id = state_file_for(left_root, right_root).stem
    manifest_dir = STATE_DIR / "deletion_plans" / pair_id
    manifest_path = manifest_dir / f"{run_id}.txt"
    trash_dir = STATE_DIR / "trash" / pair_id / run_id
    if dry_run:
        return manifest_path, trash_dir
    manifest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    with manifest_path.open("x", encoding="utf-8") as handle:
        handle.write(f"# Suppressions prévues : {timestamp}\n")
        handle.write(f"# Gauche : {left_root}\n# Droite : {right_root}\n")
        handle.write(f"# Tampon : {trash_dir}\n")
        for side, info in planned:
            handle.write(f"{side} | {info.relative_path} | {timestamp}\n")
        handle.flush()
        os.fsync(handle.fileno())
    return manifest_path, trash_dir


def cleanup_expired_trash(left_root, right_root, retention_days):
    trash_root = STATE_DIR / "trash" / state_file_for(left_root, right_root).stem
    if not trash_root.exists():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    for run_dir in trash_root.iterdir():
        if not run_dir.is_dir():
            continue
        created = datetime.fromtimestamp(run_dir.stat().st_mtime, timezone.utc)
        if created < cutoff:
            shutil.rmtree(run_dir)


def archive_file(info, root, side, trash_dir):
    source = root / info.relative_path
    if not source.is_file() or source.stat().st_size != info.size:
        raise OSError(f"Fichier modifié ou inaccessible depuis le scan : {source}")
    destination = trash_dir / side / info.relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    shutil.move(str(source), str(destination))
    cleanup_empty_parents(source, root)


def state_file_for(left_root, right_root):
    pair_id = hashlib.sha256(
        f"{left_root}|{right_root}".encode("utf-8", errors="replace")
    ).hexdigest()[:16]
    return STATE_DIR / f"{pair_id}.json"


def load_state(left_root, right_root):
    state_path = state_file_for(left_root, right_root)
    if not state_path.exists():
        return {}
    try:
        with state_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        safe_print(f"{E['WARN']}  État de synchro illisible, ignoré : {exc}")
        return {}
    return data.get("files", {})


def save_state(left_root, right_root, left_files, right_files, dry_run=False):
    if dry_run:
        return

    files = {}
    for relative_path in set(left_files) | set(right_files):
        info = left_files.get(relative_path) or right_files.get(relative_path)
        files[str(relative_path)] = {
            "size": info.size,
            "created_ns": info.created_ns,
            "modified_ns": info.modified_ns,
        }

    payload = {
        "left": str(left_root),
        "right": str(right_root),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "files": files,
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path = state_file_for(left_root, right_root)
    temp_path = state_path.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    os.replace(temp_path, state_path)


def quick_signature(root, excluded_dirs):
    files_count = 0
    total_size = 0
    newest_mtime = 0
    newest_ctime = 0

    ensure_root_available(root)

    def scan_error(exc):
        raise exc

    for current_root, dirnames, filenames in os.walk(root, onerror=scan_error):
        dirnames[:] = [
            d for d in dirnames if not should_skip_dir(d, excluded_dirs)
        ]
        for filename in filenames:
            path = Path(current_root) / filename
            stat = path.stat()
            files_count += 1
            total_size += stat.st_size
            newest_mtime = max(newest_mtime, stat.st_mtime_ns)
            newest_ctime = max(newest_ctime, stat.st_ctime_ns)

    return (files_count, total_size, newest_mtime, newest_ctime)


def choose_source(left_info, right_info, prefer):
    if left_info.sync_key == right_info.sync_key:
        return None

    # shutil.copy2 preserve la date de modification, mais Windows ne permet pas
    # de restaurer simplement la date de création. Sans cette tolérance, un
    # fichier fraîchement copié pourrait être recopié en boucle au passage suivant.
    if (
        left_info.modified_ns == right_info.modified_ns
        and left_info.size == right_info.size
    ):
        return None

    if prefer in {"left", "right"}:
        return prefer

    left_score = (left_info.modified_ns, left_info.created_ns, left_info.size)
    right_score = (right_info.modified_ns, right_info.created_ns, right_info.size)

    if left_score > right_score:
        return "left"
    if right_score > left_score:
        return "right"
    return "conflict"


def copy_file(source, destination, dry_run=False):
    if dry_run:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(f".{destination.name}.sudsync_tmp")
    shutil.copy2(source, temp_path)
    os.replace(temp_path, destination)


def cleanup_empty_parents(path, root):
    current = path.parent
    while current != root and root in current.parents:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def sync_once(
    left_root,
    right_root,
    excluded_dirs,
    prefer="newer",
    dry_run=False,
    propagate_deletes=False,
    verbose=True,
    trash_retention_days=DEFAULT_TRASH_RETENTION_DAYS,
):
    stats = SyncStats()
    if verbose:
        safe_print(f"{E['SEARCH']} Scan metadata :")
        safe_print(f"   Gauche : {left_root}")
        safe_print(f"   Droite : {right_root}")

    ensure_root_available(left_root)
    ensure_root_available(right_root)
    left_files = scan_folder(left_root, excluded_dirs)
    right_files = scan_folder(right_root, excluded_dirs)
    ensure_root_available(left_root)
    ensure_root_available(right_root)
    previous_state = load_state(left_root, right_root) if propagate_deletes else {}
    all_paths = sorted(set(left_files) | set(right_files), key=lambda p: str(p).lower())
    planned = deletion_plan(left_files, right_files, previous_state) if propagate_deletes else []
    manifest_path, trash_dir = write_deletion_manifest(
        left_root, right_root, planned, dry_run
    )
    if manifest_path and verbose:
        safe_print(f"{E['WARN']}  {len(planned)} suppression(s) prévue(s) : {manifest_path}")
        if not dry_run:
            safe_print(f"{E['FOLDER']} Tampon de restauration : {trash_dir}")
    for side, files in (("left", left_files), ("right", right_files)):
        count = sum(planned_side == side for planned_side, _ in planned)
        if files and count == len(files):
            raise RuntimeError(
                f"Suppression totale bloquée côté {side} ({count} fichiers). "
                f"Vérifiez la connexion et les deux dossiers. Liste : {manifest_path}. "
                "Aucun état mis à jour."
            )
    if not dry_run:
        cleanup_expired_trash(left_root, right_root, trash_retention_days)

    for relative_path in all_paths:
        left_info = left_files.get(relative_path)
        right_info = right_files.get(relative_path)
        left_path = left_root / relative_path
        right_path = right_root / relative_path

        try:
            if left_info and not right_info:
                if propagate_deletes and str(relative_path) in previous_state:
                    prefix = E["TEST"] if dry_run else E["WARN"]
                    if verbose:
                        safe_print(f"{prefix} Suppression propagée sur gauche : {relative_path}")
                    if not dry_run:
                        archive_file(left_info, left_root, "left", trash_dir)
                    stats.deleted_left += 1
                else:
                    prefix = E["TEST"] if dry_run else E["COPY"]
                    if verbose:
                        safe_print(f"{prefix} Gauche -> Droite : {relative_path}")
                    copy_file(left_path, right_path, dry_run=dry_run)
                    stats.copied_left_to_right += 1
            elif right_info and not left_info:
                if propagate_deletes and str(relative_path) in previous_state:
                    prefix = E["TEST"] if dry_run else E["WARN"]
                    if verbose:
                        safe_print(f"{prefix} Suppression propagée sur droite : {relative_path}")
                    if not dry_run:
                        archive_file(right_info, right_root, "right", trash_dir)
                    stats.deleted_right += 1
                else:
                    prefix = E["TEST"] if dry_run else E["COPY"]
                    if verbose:
                        safe_print(f"{prefix} Droite -> Gauche : {relative_path}")
                    copy_file(right_path, left_path, dry_run=dry_run)
                    stats.copied_right_to_left += 1
            elif left_info and right_info:
                source_side = choose_source(left_info, right_info, prefer)
                if source_side is None:
                    stats.unchanged += 1
                elif source_side == "left":
                    prefix = E["TEST"] if dry_run else E["SYNC"]
                    if verbose:
                        safe_print(f"{prefix} Plus récent gauche -> droite : {relative_path}")
                    copy_file(left_path, right_path, dry_run=dry_run)
                    stats.copied_left_to_right += 1
                elif source_side == "right":
                    prefix = E["TEST"] if dry_run else E["SYNC"]
                    if verbose:
                        safe_print(f"{prefix} Plus récent droite -> gauche : {relative_path}")
                    copy_file(right_path, left_path, dry_run=dry_run)
                    stats.copied_right_to_left += 1
                else:
                    if verbose:
                        safe_print(
                            f"{E['WARN']}  Conflit ignoré (dates identiques, contenu metadata différent) : {relative_path}"
                        )
                    stats.conflicts += 1
        except OSError as exc:
            if verbose:
                safe_print(f"{E['ERROR']} Erreur sur {relative_path} : {exc}")
            stats.errors += 1

    if not dry_run and not stats.errors:
        ensure_root_available(left_root)
        ensure_root_available(right_root)
        save_state(
            left_root,
            right_root,
            scan_folder(left_root, excluded_dirs),
            scan_folder(right_root, excluded_dirs),
        )
    return stats


def print_stats(stats, elapsed):
    safe_print("\n" + "=" * 52)
    safe_print(f"{E['CHART']} Bilan SudFolder Sync")
    safe_print(f"  {E['COPY']} Gauche -> Droite : {stats.copied_left_to_right}")
    safe_print(f"  {E['COPY']} Droite -> Gauche : {stats.copied_right_to_left}")
    safe_print(f"  {E['WARN']}  Supprimés gauche : {stats.deleted_left}")
    safe_print(f"  {E['WARN']}  Supprimés droite : {stats.deleted_right}")
    safe_print(f"  {E['SUCCESS']} Inchangés       : {stats.unchanged}")
    safe_print(f"  {E['WARN']}  Conflits ignorés  : {stats.conflicts}")
    safe_print(f"  {E['ERROR']} Erreurs          : {stats.errors}")
    safe_print(f"  {E['HOURGLASS']} Durée           : {format_duration(elapsed)}")
    safe_print("=" * 52)


def run_once(
    left_root,
    right_root,
    excluded_dirs,
    prefer,
    dry_run,
    propagate_deletes,
    verbose=True,
    trash_retention_days=DEFAULT_TRASH_RETENTION_DAYS,
):
    started = time.time()
    stats = sync_once(
        left_root,
        right_root,
        excluded_dirs,
        prefer,
        dry_run,
        propagate_deletes,
        verbose,
        trash_retention_days,
    )
    elapsed = time.time() - started
    if verbose:
        print_stats(stats, elapsed)
    return stats


def compact_status_line(
    iteration,
    last_status,
    last_stats,
    total_stats,
    last_duration,
    interval,
    remaining,
):
    return (
        f"{E['SYNC']} Pass {iteration} | next {remaining}/{interval}s | "
        f"total chg:{total_stats.changes} err:{total_stats.errors} conf:{total_stats.conflicts} | "
        f"last chg:{last_stats.changes} err:{last_stats.errors} conf:{last_stats.conflicts} | "
        f"G>D:{total_stats.copied_left_to_right} D>G:{total_stats.copied_right_to_left} "
        f"del:{total_stats.deleted_left}/{total_stats.deleted_right} | "
        f"scan:{format_duration(last_duration)} | {last_status}"
    )


def run_live(
    left_root,
    right_root,
    excluded_dirs,
    prefer,
    dry_run,
    interval,
    propagate_deletes,
    compact=False,
    trash_retention_days=DEFAULT_TRASH_RETENTION_DAYS,
):
    if not compact:
        safe_print(
            f"\n{E['SYNC']} Mode live actif : vérification toutes les {interval}s."
        )
        safe_print("Appuyez sur Ctrl+C pour arrêter.\n")

    previous_signature = None
    iteration = 1
    total_stats = SyncStats()
    last_stats = SyncStats()
    last_status = "Initialisation"
    last_duration = 0.0
    renderer = CompactRenderer() if compact else None

    try:
        while True:
            started = time.time()
            if not compact:
                safe_print(f"\n--- {E['SYNC']} Passage n°{iteration} ---")
            current_signature = (
                quick_signature(left_root, excluded_dirs),
                quick_signature(right_root, excluded_dirs),
            )

            if previous_signature == current_signature:
                last_stats = SyncStats()
                last_status = "Aucun changement metadata détecté"
                if not compact:
                    safe_print(
                        f"{E['SUCCESS']} Aucun changement metadata détecté, synchro ignorée."
                    )
            else:
                last_stats = run_once(
                    left_root,
                    right_root,
                    excluded_dirs,
                    prefer,
                    dry_run,
                    propagate_deletes,
                    verbose=not compact,
                    trash_retention_days=trash_retention_days,
                )
                add_stats(total_stats, last_stats)
                if last_stats.errors:
                    last_status = "Terminé avec erreur(s)"
                elif last_stats.conflicts:
                    last_status = "Terminé avec conflit(s)"
                elif last_stats.changes:
                    last_status = "Changements synchronisés"
                else:
                    last_status = "Scan complet, aucun changement"
                previous_signature = (
                    quick_signature(left_root, excluded_dirs),
                    quick_signature(right_root, excluded_dirs),
                )

            last_duration = time.time() - started
            iteration += 1
            if compact:
                for remaining in range(interval, 0, -1):
                    renderer.render(
                        compact_status_line(
                            iteration - 1,
                            last_status,
                            last_stats,
                            total_stats,
                            last_duration,
                            interval,
                            remaining,
                        )
                    )
                    time.sleep(1)
            else:
                safe_print(f"{E['HOURGLASS']} Attente de {interval}s...")
                time.sleep(interval)
    finally:
        if renderer:
            renderer.close()


def validate_roots(left_root, right_root):
    if not left_root.exists() or not left_root.is_dir():
        raise ValueError(f"Le dossier gauche n'existe pas : {left_root}")
    if not right_root.exists() or not right_root.is_dir():
        raise ValueError(f"Le dossier droit n'existe pas : {right_root}")
    if left_root == right_root:
        raise ValueError("Les deux dossiers doivent être différents.")
    if left_root in right_root.parents or right_root in left_root.parents:
        raise ValueError("Les deux dossiers ne doivent pas être imbriqués.")


def ask_path(label):
    while True:
        value = input(f"{E['POINTER']} {label} : ").strip()
        if value:
            return normalize_root(value)


def ask_mode():
    safe_print("\nModes :")
    safe_print("1. Lancement unique (un seul scan puis arrêt)")
    safe_print("2. Live (boucle continue)")
    while True:
        choice = input(f"{E['POINTER']} Votre choix (1-2) : ").strip()
        if choice == "1":
            return "once"
        if choice == "2":
            return "live"
        safe_print(f"{E['ERROR']} Choix invalide.")


def ask_interval():
    value = input("Intervalle en secondes (défaut 60, minimum 10) : ").strip()
    if not value:
        return 60
    try:
        return max(10, int(value))
    except ValueError:
        safe_print(f"{E['WARN']}  Valeur invalide, intervalle réglé à 60s.")
        return 60


def ask_dry_run():
    value = input("Mode test sans copie ? (o/N) : ").strip().lower()
    return value in {"o", "oui", "y", "yes"}


def build_parser():
    parser = argparse.ArgumentParser(
        description="Synchronisation bidirectionnelle simple de deux dossiers."
    )
    parser.add_argument("left", nargs="?", help="Premier dossier à synchroniser.")
    parser.add_argument("right", nargs="?", help="Second dossier à synchroniser.")
    parser.add_argument(
        "--mode",
        choices=["once", "live"],
        default=None,
        help="Mode de lancement : once ou live.",
    )
    mode_shortcuts = parser.add_mutually_exclusive_group()
    mode_shortcuts.add_argument(
        "--once",
        action="store_true",
        help="Raccourci pour --mode once : un seul scan puis arrêt.",
    )
    mode_shortcuts.add_argument(
        "--live",
        action="store_true",
        help="Raccourci pour --mode live : boucle continue.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Intervalle du mode live en secondes (minimum 10).",
    )
    parser.add_argument(
        "--prefer",
        choices=["newer", "left", "right"],
        default="newer",
        help="Stratégie si les deux fichiers existent mais diffèrent.",
    )
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Dossier à ignorer. Peut être répété.",
    )
    parser.add_argument(
        "--dry-run",
        "--test",
        action="store_true",
        help="Mode test : affiche les opérations sans copier de fichiers.",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help=(
            "Propage les suppressions connues grâce à l'état précédent. "
            "À tester d'abord avec --test."
        ),
    )
    parser.add_argument(
        "--trash-retention-days",
        type=int,
        default=DEFAULT_TRASH_RETENTION_DAYS,
        help="Conserve les fichiers dans le tampon pendant ce nombre de jours (défaut : 30).",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help=(
            "En mode live, rafraîchit un panneau de statut au lieu "
            "d'ajouter des lignes à chaque passage."
        ),
    )
    return parser


def main():
    if os.name == "nt":
        os.system("color")

    afficher_en_tete()
    parser = build_parser()
    args = parser.parse_args()
    if args.trash_retention_days < 1:
        parser.error("--trash-retention-days doit être au moins 1")

    try:
        left_root = normalize_root(args.left) if args.left else ask_path("Dossier gauche")
        right_root = normalize_root(args.right) if args.right else ask_path("Dossier droit")
        mode = args.mode
        if args.once:
            mode = "once"
        elif args.live:
            mode = "live"
        if not mode:
            mode = ask_mode()

        interval = max(10, args.interval)
        if mode == "live" and not (args.mode or args.live):
            interval = ask_interval()
        dry_run = args.dry_run if args.left and args.right else args.dry_run or ask_dry_run()
        excluded_dirs = DEFAULT_EXCLUDED_DIRS | set(args.exclude_dir)

        validate_roots(left_root, right_root)

        safe_print(
            f"\n{E['GEAR']} Comparaison basée sur date de création + date de modification + taille."
        )
        safe_print(
            f"{E['WARN']}  Les suppressions ne sont propagées qu'avec --delete."
        )
        if args.delete:
            safe_print(
                f"{E['WARN']}  Propagation des suppressions active, basée sur l'état précédent."
            )
        if dry_run:
            safe_print(
                f"{E['TEST']} Mode test actif : scan complet, affichage des modifications, aucune copie."
            )

        if mode == "live":
            run_live(
                left_root,
                right_root,
                excluded_dirs,
                args.prefer,
                dry_run,
                interval,
                args.delete,
                args.compact,
                args.trash_retention_days,
            )
        else:
            run_once(
                left_root,
                right_root,
                excluded_dirs,
                args.prefer,
                dry_run,
                args.delete,
                trash_retention_days=args.trash_retention_days,
            )

    except KeyboardInterrupt:
        safe_print(f"\n{E['BYE']} Arrêt demandé. Fermeture de SudFolder Sync.")
    except Exception as exc:
        safe_print(f"\n{E['ERROR']} {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
