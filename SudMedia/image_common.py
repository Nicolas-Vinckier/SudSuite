import io
import os
import shutil
import sys
from typing import Any, Dict, Iterable, List, Tuple

try:
    from PIL import Image
except ImportError:
    print("[Erreur] La bibliotheque 'Pillow' n'est pas installee.")
    print("Installez-la avec : pip install Pillow")
    sys.exit(1)

VALID_EXTENSIONS = (
    ".png",
    ".jpeg",
    ".jpg",
    ".webp",
    ".bmp",
    ".tiff",
    ".tif",
    ".gif",
    ".mpo",
)

IGNORED_DIRS = {"node_modules", "dist", "build", "__pycache__"}


def configure_console() -> None:
    """Enable ANSI on Windows and force UTF-8 output when possible."""
    if sys.platform == "win32":
        os.system("")
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def print_banner(title: str = "SudSuite") -> None:
    banners = {
        "master": r"""
 ____            _ __  __           _
/ ___| _   _  __| |  \/  | __ _ ___| |_ ___ _ __
\___ \| | | |/ _` | |\/| |/ _` / __| __/ _ \ '__|
 ___) | |_| | (_| | |  | | (_| \__ \ ||  __/ |
|____/ \__,_|\__,_|_|  |_|\__,_|___/\__\___|_|
""",
        "resizer": r"""
 ____            _ ____           _
/ ___| _   _  __| |  _ \ ___  ___(_)_______ _ __
\___ \| | | |/ _` | |_) / _ \/ __| |_  / _ \ '__|
 ___) | |_| | (_| |  _ <  __/\__ \ |/ /  __/ |
|____/ \__,_|\__,_|_| \_\___||___/_/___\___|_|
""",
        "convertissor": r"""
 ____            _  ____                          _
/ ___| _   _  __| |/ ___|___  _ ____   _____ _ __| |_ ___ _ __
\___ \| | | |/ _` | |   / _ \| '_ \ \ / / _ \ '__| __/ _ \ '__|
 ___) | |_| | (_| | |__| (_) | | | \ V /  __/ |  | ||  __/ |
|____/ \__,_|\__,_|\____\___/|_| |_|\_/ \___|_|   \__\___|_|
""",
        "compressor": r"""
 ____            _  ____
/ ___| _   _  __| |/ ___|___  _ __ ___  _ __  _ __ ___  ___ ___  ___  _ __
\___ \| | | |/ _` | |   / _ \| '_ ` _ \| '_ \| '__/ _ \/ __/ __|/ _ \| '__|
 ___) | |_| | (_| | |__| (_) | | | | | | |_) | | |  __/\__ \__ \ (_) | |
|____/ \__,_|\__,_|\____\___/|_| |_| |_| .__/|_|  \___||___/___/\___/|_|
                                        |_|
""",
    }
    print(banners.get(title, title))


def format_size(size_in_bytes: int) -> str:
    size = float(size_in_bytes)
    for unit in ["O", "Ko", "Mo", "Go"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} To"


def truncate_text(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return text[: max_len - 3] + "..."


def ask_input_paths(prompt: str) -> List[str]:
    raw = input(prompt).strip().strip('"')
    return [raw] if raw else []


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    answer = input(prompt).strip().lower()
    if not answer:
        return default
    return answer in ("o", "oui", "y", "yes")


def ask_output_dir(
    paths: List[str],
    files: List[str],
    default_folder_name: str = "output_processed",
    batch_suffix: str = "_processed",
    prompt: bool = True,
) -> str:
    if len(files) == 1:
        default_out = os.path.dirname(os.path.abspath(files[0]))
    elif paths and os.path.isdir(paths[0]):
        default_out = paths[0].rstrip("/\\") + batch_suffix
    elif paths:
        default_out = os.path.join(os.path.dirname(os.path.abspath(paths[0])), default_folder_name)
    else:
        default_out = os.path.abspath(default_folder_name)

    if prompt:
        chosen = input(f"\nDossier de sortie (defaut: {default_out}) : ").strip().strip('"')
        output_dir = chosen or default_out
    else:
        output_dir = default_out

    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def get_target_files(paths: Iterable[str], valid_extensions: Tuple[str, ...] = VALID_EXTENSIONS) -> List[str]:
    target_files: List[str] = []
    for raw_path in paths:
        path = raw_path.strip().strip('"')
        if not path:
            continue
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                dirs[:] = [
                    directory
                    for directory in dirs
                    if not directory.startswith((".", "__")) and directory not in IGNORED_DIRS
                ]
                for filename in files:
                    if filename.lower().endswith(valid_extensions):
                        target_files.append(os.path.join(root, filename))
        elif os.path.isfile(path):
            if path.lower().endswith(valid_extensions):
                target_files.append(path)
            else:
                print(f"[Alerte] Fichier ignore, extension non supportee : {path}")
        else:
            print(f"[Alerte] Chemin introuvable : {path}")

    return sorted(dict.fromkeys(target_files))


def get_image_infos(files: Iterable[str]) -> List[Dict[str, Any]]:
    image_infos: List[Dict[str, Any]] = []
    for file_path in files:
        try:
            with Image.open(file_path) as img:
                width, height = img.size
                image_format = img.format or "UNKNOWN"

            size_bytes = os.path.getsize(file_path)
            ratio_hw = height / width if width else 0

            image_infos.append(
                {
                    "path": file_path,
                    "name": os.path.basename(file_path),
                    "width": width,
                    "height": height,
                    "format": image_format,
                    "size_bytes": size_bytes,
                    "ratio_hw": ratio_hw,
                }
            )
        except Exception as exc:
            print(f"[Alerte] Impossible de lire l'image {file_path}: {exc}")
    return image_infos


def print_image_table(image_infos: List[Dict[str, Any]]) -> None:
    if not image_infos:
        return

    name_width = max(len(info["name"]) for info in image_infos)
    name_width = min(max(name_width, 20), 45)

    columns = [
        ("Nom", name_width),
        ("Taille", 13),
        ("Poids", 12),
        ("Ratio H/L", 12),
    ]
    separator = "+-" + "-+-".join("-" * width for _, width in columns) + "-+"

    def print_row(values: List[str]) -> None:
        row = "| "
        for value, (_, width) in zip(values, columns):
            row += str(value).ljust(width) + " | "
        print(row.rstrip())

    print("\n--- IMAGES DETECTEES ---")
    print(separator)
    print_row([title for title, _ in columns])
    print(separator)

    total_size = 0
    for info in image_infos:
        total_size += info["size_bytes"]
        print_row(
            [
                truncate_text(info["name"], name_width),
                f"{info['width']}x{info['height']}",
                format_size(info["size_bytes"]),
                f"{info['ratio_hw']:.4f}",
            ]
        )

    print(separator)
    print(f"Poids total detecte : {format_size(total_size)}")


def get_total_size(files: Iterable[str]) -> int:
    total = 0
    for file_path in files:
        try:
            if os.path.isfile(file_path):
                total += os.path.getsize(file_path)
        except OSError:
            pass
    return total


def render_progress(
    global_idx: int,
    global_total: int,
    filename: str,
    step: int = 0,
    total_steps: int = 100,
    status: str = "",
) -> None:
    try:
        columns = shutil.get_terminal_size((80, 20)).columns
    except Exception:
        columns = 80

    safety_margin = 15
    available_width = columns - safety_margin
    g_bar_len = 10
    l_bar_len = 8

    g_filled = int(g_bar_len * global_idx // global_total) if global_total > 0 else 0
    g_bar = "#" * g_filled + "." * (g_bar_len - g_filled)
    g_pct = (global_idx / global_total * 100) if global_total > 0 else 0

    l_filled = int(l_bar_len * step // total_steps) if total_steps > 0 else 0
    l_bar = "=" * l_filled + " " * (l_bar_len - l_filled)

    fn = os.path.basename(filename)
    txt_space = available_width - 45
    if len(fn) > txt_space:
        fn = fn[: max(5, txt_space - 3)] + "..."

    line = f" G:[{g_bar}] {g_pct:>3.0f}% ({global_idx}/{global_total}) | {status:<11} | [{l_bar}] | {fn}"
    sys.stdout.write("\r" + line.ljust(max(columns - 1, 1)))
    sys.stdout.flush()


def make_unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path

    folder, filename = os.path.split(path)
    base, ext = os.path.splitext(filename)
    counter = 2
    while True:
        candidate = os.path.join(folder, f"{base}_{counter}{ext}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def avoid_same_input_output(input_path: str, output_path: str, suffix: str = "_new") -> str:
    if os.path.abspath(input_path) != os.path.abspath(output_path):
        return output_path

    folder, filename = os.path.split(output_path)
    base, ext = os.path.splitext(filename)
    return os.path.join(folder, f"{base}{suffix}{ext}")


def normalize_quality(value: Any, default: int = 75) -> int:
    try:
        quality = int(value)
    except (TypeError, ValueError):
        quality = default
    return max(1, min(100, quality))


def normalize_save_format(format_name: Any) -> str:
    save_format = str(format_name or "PNG").upper()
    if save_format in ("JPG", "JPEG", "MPO"):
        return "JPEG"
    if save_format in ("TIF", "TIFF"):
        return "TIFF"
    if save_format in ("PNG", "WEBP", "GIF", "BMP"):
        return save_format
    return "PNG"


def source_save_format_from_image(img: Image.Image) -> str:
    return normalize_save_format(img.format or "PNG")


def extension_for_format(save_format: str) -> str:
    normalized = normalize_save_format(save_format)
    if normalized == "JPEG":
        return ".jpg"
    if normalized == "TIFF":
        return ".tiff"
    return f".{normalized.lower()}"
