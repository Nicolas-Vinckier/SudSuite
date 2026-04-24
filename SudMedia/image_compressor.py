import io
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
    extension_for_format,
    format_size,
    get_image_infos,
    get_target_files,
    get_total_size,
    normalize_quality,
    print_banner,
    print_image_table,
    render_progress,
    source_save_format_from_image,
)

try:
    ADAPTIVE_PALETTE = Image.Palette.ADAPTIVE
except AttributeError:
    ADAPTIVE_PALETTE = Image.ADAPTIVE

try:
    FASTOCTREE = Image.Quantize.FASTOCTREE
except AttributeError:
    FASTOCTREE = 2


def ask_compress_config(allow_webp_choice: bool = True) -> Dict[str, Any]:
    print("\n--- CONFIGURATION COMPRESSION ---")
    print("1. Sans perte : optimisation sans degradation volontaire")
    print("2. Avec perte : reduction de qualite pour reduire le poids")

    mode = input("Mode (1 ou 2) : ").strip() or "1"
    if mode not in ("1", "2"):
        raise ValueError("Mode de compression invalide.")

    config: Dict[str, Any] = {
        "mode": mode,
        "choix": mode,
        "quality": None,
        "use_webp": False,
        "skip_if_larger": True,
    }

    if mode == "2":
        quality_raw = input("Qualite (1-100, defaut 75) : ").strip() or "75"
        config["quality"] = normalize_quality(quality_raw, default=75)
        if allow_webp_choice:
            config["use_webp"] = ask_yes_no(
                "Convertir en WebP pour maximiser le gain ? (O/n) : ",
                default=True,
            )
        else:
            config["use_webp"] = False

    return config


def normalize_compress_config(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    normalized = dict(config or {})
    if "mode" not in normalized and "choix" in normalized:
        normalized["mode"] = normalized["choix"]
    if "choix" not in normalized and "mode" in normalized:
        normalized["choix"] = normalized["mode"]
    normalized.setdefault("mode", "1")
    normalized.setdefault("choix", normalized["mode"])
    normalized.setdefault("quality", None)
    normalized.setdefault("use_webp", False)
    normalized.setdefault("skip_if_larger", True)
    if str(normalized.get("mode")) == "2":
        normalized["quality"] = normalize_quality(normalized.get("quality"), default=75)
    return normalized


def compression_mode_label(config: Optional[Dict[str, Any]]) -> str:
    normalized = normalize_compress_config(config)
    mode = str(normalized.get("mode", "1"))
    if mode == "1":
        return "lossless"
    quality = normalize_quality(normalized.get("quality"), default=75)
    return f"lossy-q{quality}"


def get_original_quality(img: Image.Image) -> int:
    try:
        return int(img.info.get("quality", 100))
    except (TypeError, ValueError):
        return 100


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


def prepare_for_webp(img: Image.Image) -> Image.Image:
    if image_has_alpha(img):
        return img.convert("RGBA")
    if img.mode not in ("RGB", "RGBA"):
        return img.convert("RGB")
    return img


def _save_lossless_to_buffer(img: Image.Image, save_format: str) -> io.BytesIO:
    buffer = io.BytesIO()
    save_format = str(save_format).upper()

    if save_format == "JPEG":
        working = flatten_transparency_on_white(img)
        try:
            working.save(buffer, format="JPEG", optimize=True, quality="keep")
        except Exception:
            quality = get_original_quality(img)
            kwargs: Dict[str, Any] = {"quality": quality, "optimize": True}
            if quality >= 95:
                kwargs["subsampling"] = 0
            working.save(buffer, format="JPEG", **kwargs)
    elif save_format == "PNG":
        working = img.convert("RGBA") if image_has_alpha(img) else img.convert("RGB")
        working.save(buffer, format="PNG", optimize=True)
    elif save_format == "WEBP":
        working = prepare_for_webp(img)
        working.save(
            buffer,
            format="WEBP",
            lossless=True,
            quality=100,
            method=0 if image_has_alpha(working) else 6,
        )
    elif save_format == "GIF":
        working = img if img.mode == "P" else img.convert("P", palette=ADAPTIVE_PALETTE)
        working.save(buffer, format="GIF", optimize=True)
    elif save_format == "TIFF":
        img.save(buffer, format="TIFF", compression="tiff_lzw")
    elif save_format == "BMP":
        flatten_transparency_on_white(img).save(buffer, format="BMP")
    else:
        img.save(buffer, format=save_format)

    return buffer


def _save_lossy_to_buffer(img: Image.Image, save_format: str, quality: int) -> io.BytesIO:
    buffer = io.BytesIO()
    save_format = str(save_format).upper()

    if save_format == "JPEG":
        working = flatten_transparency_on_white(img)
        working.save(buffer, format="JPEG", optimize=True, quality=quality)
    elif save_format == "WEBP":
        working = prepare_for_webp(img)
        working.save(buffer, format="WEBP", quality=quality, method=4)
    elif save_format == "PNG":
        colors = max(2, int((quality / 100) * 256))
        if image_has_alpha(img):
            working = img.convert("RGBA").quantize(colors=colors, method=FASTOCTREE)
        else:
            working = img.convert("RGB").convert("P", palette=ADAPTIVE_PALETTE, colors=colors)
        working.save(buffer, format="PNG", optimize=True)
    elif save_format == "GIF":
        colors = max(2, int((quality / 100) * 256))
        working = img.convert("RGB").convert("P", palette=ADAPTIVE_PALETTE, colors=colors)
        working.save(buffer, format="GIF", optimize=True)
    else:
        return _save_lossless_to_buffer(img, save_format)

    return buffer


def compress_pil_image_to_buffer(img: Image.Image, save_format: str, config: Dict[str, Any]) -> io.BytesIO:
    """Encode an already opened PIL image into a compressed buffer without writing a file."""
    normalized = normalize_compress_config(config)
    mode = str(normalized.get("mode", "1"))
    if mode == "1":
        return _save_lossless_to_buffer(img, save_format)
    if mode == "2":
        quality = normalize_quality(normalized.get("quality"), default=75)
        return _save_lossy_to_buffer(img, save_format, quality)
    raise ValueError("Mode de compression invalide.")


def _build_output_path(input_path: str, output_dir: str, save_format: str, config: Dict[str, Any]) -> str:
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    suffix = compression_mode_label(config)
    output_ext = extension_for_format(save_format)
    return os.path.join(output_dir, f"{base_name}_compress-{suffix}{output_ext}")


def compress_one_image(
    input_path: str,
    output_dir: str,
    config: Dict[str, Any],
    global_info: Tuple[int, int] = (1, 1),
    show_progress: bool = True,
) -> Dict[str, Any]:
    idx, total = global_info
    original_size = os.path.getsize(input_path)
    normalized_config = normalize_compress_config(config)

    if show_progress:
        render_progress(idx - 1, total, input_path, 20, 100, "Ouverture")
        time.sleep(0.01)

    with Image.open(input_path) as source_img:
        save_format = source_save_format_from_image(source_img)
        if str(normalized_config.get("mode")) == "2" and normalized_config.get("use_webp", False):
            save_format = "WEBP"
        img = source_img.copy()

    output_path = _build_output_path(input_path, output_dir, save_format, normalized_config)

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
        render_progress(idx - 1, total, input_path, 65, 100, "Compression")
        time.sleep(0.01)

    buffer = compress_pil_image_to_buffer(img, save_format, normalized_config)
    new_size = buffer.tell()
    skip_if_larger = bool(normalized_config.get("skip_if_larger", True))

    if skip_if_larger and new_size >= original_size:
        if show_progress:
            render_progress(idx, total, input_path, 100, 100, "Sans gain")
        return {
            "status": "skipped_no_gain",
            "input": input_path,
            "output": input_path,
            "original_size": original_size,
            "new_size": original_size,
        }

    with open(output_path, "wb") as handle:
        handle.write(buffer.getvalue())

    if show_progress:
        render_progress(idx, total, input_path, 100, 100, "Termine")

    return {
        "status": "success",
        "input": input_path,
        "output": output_path,
        "original_size": original_size,
        "new_size": new_size,
    }


def compress_images(
    files: List[str],
    output_dir: str,
    config: Dict[str, Any],
    show_progress: bool = True,
) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    output_files: List[str] = []
    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    success_count = 0
    skipped_count = 0
    total = len(files)
    normalized_config = normalize_compress_config(config)

    for idx, input_path in enumerate(files, 1):
        try:
            result = compress_one_image(
                input_path,
                output_dir,
                normalized_config,
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
            print(f"\n[Erreur] Compression impossible pour {input_path}: {exc}")

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


def compress_image(
    input_path: str,
    settings: Optional[Dict[str, Any]] = None,
    output_dir: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Backward-compatible helper for older calls."""
    if settings is None:
        settings = ask_compress_config()
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(input_path))
    result = compress_one_image(input_path, output_dir, settings, global_info=(1, 1), show_progress=False)
    if result["status"] == "success":
        print(f"Succes : {os.path.basename(result['output'])}")
        print(f"Nouvelle taille : {format_size(result['new_size'])}")
    elif result["status"] == "skipped_no_gain":
        print("Aucun gain : fichier original conserve.")
    return result


def main() -> None:
    configure_console()
    print_banner("compressor")

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
        config = ask_compress_config()
    except ValueError as exc:
        print(f"[Erreur] {exc}")
        sys.exit(1)

    output_dir = ask_output_dir(paths, files, default_folder_name="compressed", batch_suffix="_compressed")
    print(f"Sortie : {output_dir}")

    if not ask_yes_no(f"Compresser {len(files)} image(s) ? (O/n) : ", default=True):
        print("Operation annulee.")
        sys.exit(0)

    start_time = time.time()
    result = compress_images(files, output_dir, config, show_progress=True)
    duration = time.time() - start_time

    print("\n" + "=" * 45)
    print("BILAN COMPRESSION")
    print("=" * 45)
    print(f"Images compressees : {result['success_count']}/{len(files)}")
    if result["skipped_count"]:
        print(f"Images ignorees    : {result['skipped_count']}")
    print(f"Temps ecoule       : {duration:.2f} secondes")
    print(f"Taille initiale    : {format_size(result['original_size'])}")
    print(f"Taille finale      : {format_size(result['final_size'])}")

    diff = result["final_size"] - result["original_size"]
    if diff < 0:
        percent = abs(diff) / result["original_size"] * 100 if result["original_size"] else 0
        print(f"Gain d'espace      : {format_size(abs(diff))} ({percent:.1f}%)")
    else:
        print(f"Augmentation       : {format_size(diff)}")
    print(f"Sortie             : {output_dir}")
    print("=" * 45)


if __name__ == "__main__":
    main()
