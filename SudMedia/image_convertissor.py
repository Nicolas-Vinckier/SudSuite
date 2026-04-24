import os
import sys
import time
from typing import Any, Dict, List, Tuple

from PIL import Image

from image_common import (
    ask_input_paths,
    ask_output_dir,
    ask_yes_no,
    avoid_same_input_output,
    configure_console,
    format_size,
    get_image_infos,
    get_target_files,
    get_total_size,
    print_banner,
    print_image_table,
    render_progress,
)

SUPPORTED_OUTPUT_FORMATS = {
    "1": ("PNG", ".png"),
    "2": ("JPEG", ".jpg"),
    "3": ("WEBP", ".webp"),
    "4": ("BMP", ".bmp"),
    "5": ("TIFF", ".tiff"),
    "6": ("GIF", ".gif"),
}


def ask_convert_config() -> Dict[str, str]:
    print("\n--- CONFIGURATION CONVERSION ---")
    for key, (fmt, _) in SUPPORTED_OUTPUT_FORMATS.items():
        print(f"  {key}. {fmt}")

    choice = input("Format cible (numero) : ").strip()
    if choice not in SUPPORTED_OUTPUT_FORMATS:
        raise ValueError("Format cible invalide.")

    target_format, target_ext = SUPPORTED_OUTPUT_FORMATS[choice]
    return {"format": target_format, "ext": target_ext}


def image_has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)


def flatten_transparency_on_white(img: Image.Image) -> Image.Image:
    if image_has_alpha(img):
        rgba = img.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        background.alpha_composite(rgba)
        return background.convert("RGB")
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def prepare_image_for_format(img: Image.Image, target_format: str) -> Image.Image:
    target_format = str(target_format).upper()

    if target_format in ("JPEG", "BMP"):
        return flatten_transparency_on_white(img)

    if target_format == "GIF":
        if img.mode == "P":
            return img
        if image_has_alpha(img):
            return img.convert("RGBA").convert("P", palette=Image.Palette.ADAPTIVE)
        return img.convert("P", palette=Image.Palette.ADAPTIVE)

    if target_format in ("PNG", "WEBP", "TIFF"):
        if img.mode == "P" and "transparency" in img.info:
            return img.convert("RGBA")
        return img

    return img


def save_params_for_format(target_format: str, img: Image.Image) -> Dict[str, Any]:
    target_format = str(target_format).upper()

    if target_format == "WEBP":
        method = 0 if image_has_alpha(img) else 6
        return {"lossless": True, "quality": 100, "method": method}
    if target_format == "JPEG":
        return {"quality": 100, "subsampling": 0, "optimize": True}
    if target_format == "PNG":
        return {"optimize": True}
    if target_format == "TIFF":
        return {"compression": "tiff_lzw"}
    if target_format == "GIF":
        return {"optimize": True}
    return {}


def convert_pil_image(img: Image.Image, config: Dict[str, str]) -> Tuple[Image.Image, str, str]:
    """Convert an opened PIL image without writing it. Used by image_master."""
    target_format = config["format"]
    target_ext = config["ext"]
    return prepare_image_for_format(img, target_format), target_format, target_ext


def convert_one_image(
    input_path: str,
    output_dir: str,
    config: Dict[str, str],
    global_info: Tuple[int, int] = (1, 1),
    show_progress: bool = True,
) -> Dict[str, Any]:
    idx, total = global_info
    target_format = config["format"]
    target_ext = config["ext"]

    original_size = os.path.getsize(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}{target_ext}")
    output_path = avoid_same_input_output(input_path, output_path, suffix="_converted")

    if os.path.exists(output_path):
        if show_progress:
            render_progress(idx, total, input_path, 100, 100, "Ignore")
        return {
            "status": "skipped_existing",
            "input": input_path,
            "output": output_path,
            "original_size": original_size,
            "new_size": os.path.getsize(output_path),
        }

    if show_progress:
        render_progress(idx - 1, total, input_path, 20, 100, "Ouverture")
        time.sleep(0.01)

    with Image.open(input_path) as source_img:
        img = source_img.copy()

    if show_progress:
        render_progress(idx - 1, total, input_path, 60, 100, "Conversion")
        time.sleep(0.01)

    img = prepare_image_for_format(img, target_format)
    img.save(output_path, format=target_format, **save_params_for_format(target_format, img))

    new_size = os.path.getsize(output_path)

    if show_progress:
        render_progress(idx, total, input_path, 100, 100, "Termine")

    return {
        "status": "success",
        "input": input_path,
        "output": output_path,
        "original_size": original_size,
        "new_size": new_size,
    }


def convert_images(
    files: List[str],
    output_dir: str,
    config: Dict[str, str],
    show_progress: bool = True,
) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    output_files: List[str] = []
    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    success_count = 0
    skipped_count = 0
    total = len(files)

    for idx, input_path in enumerate(files, 1):
        try:
            result = convert_one_image(
                input_path,
                output_dir,
                config,
                global_info=(idx, total),
                show_progress=show_progress,
            )
            results.append(result)
            output_files.append(result["output"])
            if result["status"] == "success":
                success_count += 1
            else:
                skipped_count += 1
        except Exception as exc:
            errors.append({"file": input_path, "error": str(exc)})
            print(f"\n[Erreur] Conversion impossible pour {input_path}: {exc}")

    if show_progress:
        print()

    return {
        "files": output_files,
        "success_count": success_count,
        "skipped_count": skipped_count,
        "errors": errors,
        "results": results,
        "original_size": get_total_size(files),
        "final_size": get_total_size(output_files),
    }


def main() -> None:
    configure_console()
    print_banner("convertissor")

    paths = sys.argv[1:] if len(sys.argv) > 1 else ask_input_paths("Chemin image ou dossier : ")
    if not paths:
        print("[Erreur] Aucun chemin specifie.")
        sys.exit(0)

    files = get_target_files(paths)
    if not files:
        print("[Erreur] Aucune image valide trouvee.")
        sys.exit(1)

    image_infos = get_image_infos(files)
    print(f"{len(image_infos)} image(s) detectee(s).")
    print_image_table(image_infos)

    try:
        config = ask_convert_config()
    except ValueError as exc:
        print(f"[Erreur] {exc}")
        sys.exit(1)

    output_dir = ask_output_dir(paths, files, default_folder_name="converted", batch_suffix="_convert")
    print(f"Sortie : {output_dir}")

    if not ask_yes_no(f"Convertir {len(files)} image(s) en {config['format']} ? (O/n) : ", default=True):
        print("Operation annulee.")
        sys.exit(0)

    start_time = time.time()
    result = convert_images(files, output_dir, config, show_progress=True)
    duration = time.time() - start_time

    print("\n" + "=" * 45)
    print("BILAN CONVERSION")
    print("=" * 45)
    print(f"Images converties : {result['success_count']}/{len(files)}")
    if result["skipped_count"]:
        print(f"Images ignorees   : {result['skipped_count']}")
    print(f"Temps ecoule      : {duration:.2f} secondes")
    print(f"Taille initiale   : {format_size(result['original_size'])}")
    print(f"Taille finale     : {format_size(result['final_size'])}")
    print(f"Sortie            : {output_dir}")
    print("=" * 45)


if __name__ == "__main__":
    main()
