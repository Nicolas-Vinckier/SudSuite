import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image
from image_common import (
    ask_input_paths,
    ask_output_dir,
    ask_yes_no,
    configure_console,
    format_size,
    get_image_infos,
    get_target_files,
    get_total_size,
    make_unique_path,
    print_banner,
    print_image_table,
    render_progress,
)

try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE = Image.LANCZOS

RESIZE_METHODS = {
    "1": "Remplissage (recadrage centre)",
    "2": "Adaptation (bandes transparentes)",
    "3": "Etirage (deformation possible)",
}


def parse_positive_int(value: str, label: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{label} invalide : entrez un entier positif ou x.") from exc

    if parsed <= 0:
        raise ValueError(f"{label} invalide : la valeur doit etre superieure a 0.")

    return parsed


def parse_dimension_inputs(w_input: str, h_input: str) -> Tuple[Optional[int], Optional[int], bool, bool]:
    w_raw = w_input.strip().lower()
    h_raw = h_input.strip().lower()

    if not w_raw or not h_raw:
        raise ValueError("Largeur et hauteur sont obligatoires.")

    width_auto = w_raw == "x"
    height_auto = h_raw == "x"

    if width_auto and height_auto:
        raise ValueError("Largeur et hauteur ne peuvent pas toutes les deux valoir x.")

    target_w = None if width_auto else parse_positive_int(w_raw, "Largeur")
    target_h = None if height_auto else parse_positive_int(h_raw, "Hauteur")

    return target_w, target_h, width_auto, height_auto


def resolve_target_dimensions(
    src_w: int,
    src_h: int,
    target_w: Optional[int],
    target_h: Optional[int],
    width_auto: bool,
    height_auto: bool,
) -> Tuple[int, int]:
    if src_w <= 0 or src_h <= 0:
        raise ValueError("Dimensions source invalides.")

    if width_auto:
        if target_h is None:
            raise ValueError("Hauteur manquante pour calculer la largeur automatique.")
        resolved_w = int(round(target_h * src_w / src_h))
        resolved_h = target_h
    elif height_auto:
        if target_w is None:
            raise ValueError("Largeur manquante pour calculer la hauteur automatique.")
        resolved_w = target_w
        resolved_h = int(round(target_w * src_h / src_w))
    else:
        if target_w is None or target_h is None:
            raise ValueError("Dimensions cibles incompletes.")
        resolved_w = target_w
        resolved_h = target_h

    return max(1, resolved_w), max(1, resolved_h)


def format_dimension_mode(config: Dict[str, Any]) -> str:
    w_label = "auto" if config.get("width_auto") else str(config.get("target_w"))
    h_label = "auto" if config.get("height_auto") else str(config.get("target_h"))
    return f"{w_label}x{h_label}"


def ask_resize_config() -> Dict[str, Any]:
    print("\n--- CONFIGURATION REDIMENSIONNEMENT ---")
    print("Utilisez x pour calculer automatiquement une dimension.")
    print("Exemples : largeur 800 + hauteur x, ou largeur x + hauteur 500.")

    w_input = input("Largeur cible : ").strip()
    h_input = input("Hauteur cible : ").strip()
    target_w, target_h, width_auto, height_auto = parse_dimension_inputs(w_input, h_input)

    print("\nMethodes :")
    for key, label in RESIZE_METHODS.items():
        print(f"  {key}. {label}")

    method = input("Methode (defaut 1) : ").strip() or "1"
    if method not in RESIZE_METHODS:
        print("[Alerte] Methode invalide, utilisation de 1.")
        method = "1"

    config = {
        "target_w": target_w,
        "target_h": target_h,
        "width_auto": width_auto,
        "height_auto": height_auto,
        "method": method,
    }

    print(f"Mode dimensions : {format_dimension_mode(config)}")
    if width_auto or height_auto:
        print("La valeur automatique sera calculee image par image.")

    return config


def _prepare_image_for_png(img: Image.Image) -> Image.Image:
    if img.mode in ("RGB", "RGBA"):
        return img
    if img.mode == "P" and "transparency" in img.info:
        return img.convert("RGBA")
    if "A" in img.mode:
        return img.convert("RGBA")
    return img.convert("RGB")


def resize_image_fill(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    target_ratio = target_w / target_h

    if src_ratio > target_ratio:
        new_h = target_h
        new_w = int(round(src_w * (target_h / src_h)))
        resized = img.resize((new_w, new_h), RESAMPLE)
        left = (new_w - target_w) // 2
        return resized.crop((left, 0, left + target_w, target_h))

    new_w = target_w
    new_h = int(round(src_h * (target_w / src_w)))
    resized = img.resize((new_w, new_h), RESAMPLE)
    top = (new_h - target_h) // 2
    return resized.crop((0, top, target_w, top + target_h))


def resize_image_fit(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    working = img.copy()
    working.thumbnail((target_w, target_h), RESAMPLE)
    new_img = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    if working.mode != "RGBA":
        working = _prepare_image_for_png(working)
        if working.mode != "RGBA":
            working = working.convert("RGBA")
    offset = ((target_w - working.width) // 2, (target_h - working.height) // 2)
    new_img.paste(working, offset, working if working.mode == "RGBA" else None)
    return new_img


def resize_image_stretch(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    return img.resize((target_w, target_h), RESAMPLE)


def resize_image(img: Image.Image, target_w: int, target_h: int, method: str) -> Image.Image:
    img = _prepare_image_for_png(img)
    if method == "1":
        return resize_image_fill(img, target_w, target_h)
    if method == "2":
        return resize_image_fit(img, target_w, target_h)
    return resize_image_stretch(img, target_w, target_h)


def resize_pil_image(img: Image.Image, config: Dict[str, Any]) -> Tuple[Image.Image, int, int]:
    """Resize an already opened PIL image. Used by image_master to avoid intermediate files."""
    src_w, src_h = img.size
    target_w, target_h = resolve_target_dimensions(
        src_w,
        src_h,
        config.get("target_w"),
        config.get("target_h"),
        bool(config.get("width_auto")),
        bool(config.get("height_auto")),
    )
    resized = resize_image(img, target_w, target_h, str(config.get("method", "1")))
    return resized, target_w, target_h


def resize_one_image(
    input_path: str,
    output_dir: str,
    config: Dict[str, Any],
    global_info: Tuple[int, int] = (1, 1),
    show_progress: bool = True,
) -> Dict[str, Any]:
    idx, total = global_info
    original_size = os.path.getsize(input_path)

    if show_progress:
        render_progress(idx - 1, total, input_path, 15, 100, "Ouverture")
        time.sleep(0.01)

    with Image.open(input_path) as source_img:
        resized, target_w, target_h = resize_pil_image(source_img.copy(), config)

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_filename = f"{base_name}_{target_w}x{target_h}.png"
    output_path = make_unique_path(os.path.join(output_dir, output_filename))

    if show_progress:
        render_progress(idx - 1, total, input_path, 70, 100, "Resize")
        time.sleep(0.01)

    resized.save(output_path, format="PNG", optimize=True)
    new_size = os.path.getsize(output_path)

    if show_progress:
        render_progress(idx, total, input_path, 100, 100, "Termine")

    return {
        "status": "success",
        "input": input_path,
        "output": output_path,
        "original_size": original_size,
        "new_size": new_size,
        "width": target_w,
        "height": target_h,
    }


def resize_images(
    files: List[str],
    output_dir: str,
    config: Dict[str, Any],
    show_progress: bool = True,
) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    results: List[Dict[str, Any]] = []
    output_files: List[str] = []
    errors: List[Dict[str, str]] = []
    total = len(files)

    for idx, input_path in enumerate(files, 1):
        try:
            result = resize_one_image(
                input_path,
                output_dir,
                config,
                global_info=(idx, total),
                show_progress=show_progress,
            )
            results.append(result)
            output_files.append(result["output"])
        except Exception as exc:
            errors.append({"file": input_path, "error": str(exc)})
            print(f"\n[Erreur] Redimensionnement impossible pour {input_path}: {exc}")

    if show_progress:
        print()

    return {
        "files": output_files,
        "success_count": len(output_files),
        "errors": errors,
        "results": results,
        "original_size": get_total_size(files),
        "final_size": get_total_size(output_files),
    }


def main() -> None:
    configure_console()
    print_banner("resizer")

    paths = sys.argv[1:] if len(sys.argv) > 1 else ask_input_paths("Chemin image ou dossier : ")
    if not paths:
        print("[Erreur] Aucun chemin specifie.")
        sys.exit(0)

    files = get_target_files(paths)
    if not files:
        print("[Erreur] Aucune image valide trouvee.")
        sys.exit(1)

    image_infos = get_image_infos(files)
    if not image_infos:
        print("[Erreur] Aucune image lisible trouvee.")
        sys.exit(1)

    print(f"{len(image_infos)} image(s) detectee(s).")
    print_image_table(image_infos)

    try:
        config = ask_resize_config()
    except ValueError as exc:
        print(f"[Erreur] {exc}")
        sys.exit(1)

    output_dir = ask_output_dir(paths, files, default_folder_name="resized", batch_suffix="_resized")
    print(f"Sortie : {output_dir}")

    if not ask_yes_no(f"Lancer le redimensionnement sur {len(files)} image(s) ? (O/n) : ", default=True):
        print("Operation annulee.")
        sys.exit(0)

    start_time = time.time()
    result = resize_images(files, output_dir, config, show_progress=True)
    duration = time.time() - start_time

    print("\n" + "=" * 45)
    print("BILAN REDIMENSIONNEMENT")
    print("=" * 45)
    print(f"Images traitees : {result['success_count']}/{len(files)}")
    print(f"Temps ecoule    : {duration:.2f} secondes")
    print(f"Taille initiale : {format_size(result['original_size'])}")
    print(f"Taille finale   : {format_size(result['final_size'])}")
    print(f"Sortie          : {output_dir}")
    print("=" * 45)


if __name__ == "__main__":
    main()
