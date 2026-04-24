import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from image_common import (
    ask_input_paths,
    ask_output_dir,
    ask_yes_no,
    avoid_same_input_output,
    configure_console,
    extension_for_format,
    format_size,
    get_image_infos,
    get_target_files,
    get_total_size,
    make_unique_path,
    print_banner,
    print_image_table,
    render_progress,
    source_save_format_from_image,
)
from image_resizer import ask_resize_config, format_dimension_mode, resize_pil_image
from image_convertissor import ask_convert_config, prepare_image_for_format, save_params_for_format
from image_compressor import (
    ask_compress_config,
    compress_pil_image_to_buffer,
    compression_mode_label,
    normalize_compress_config,
)


def _determine_target_format(
    source_format: str,
    do_resize: bool,
    do_convert: bool,
    convert_config: Optional[Dict[str, Any]],
    do_compress: bool,
    compress_config: Optional[Dict[str, Any]],
) -> str:
    if do_convert and convert_config:
        return str(convert_config["format"]).upper()

    normalized_compress = normalize_compress_config(compress_config)
    if do_compress and str(normalized_compress.get("mode")) == "2" and normalized_compress.get("use_webp", False):
        return "WEBP"

    if do_resize:
        # The standalone resizer also writes PNG. Keeping this behavior avoids
        # alpha/transparency problems after letterbox resizing.
        return "PNG"

    return source_format


def _build_final_output_path(
    input_path: str,
    output_dir: str,
    output_format: str,
    resize_dimensions: Optional[Tuple[int, int]],
    do_compress: bool,
    compress_config: Optional[Dict[str, Any]],
) -> str:
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    ext = extension_for_format(output_format)

    parts = [base_name]
    if resize_dimensions is not None:
        width, height = resize_dimensions
        parts.append(f"{width}x{height}")
    if do_compress:
        parts.append(f"compress-{compression_mode_label(compress_config)}")

    output_name = "_".join(parts) + ext
    output_path = os.path.join(output_dir, output_name)
    output_path = avoid_same_input_output(input_path, output_path, suffix="_final")
    return make_unique_path(output_path)


def process_workflow_image(
    input_path: str,
    output_dir: str,
    do_resize: bool,
    resize_config: Optional[Dict[str, Any]],
    do_convert: bool,
    convert_config: Optional[Dict[str, Any]],
    do_compress: bool,
    compress_config: Optional[Dict[str, Any]],
    global_info: Tuple[int, int] = (1, 1),
    show_progress: bool = True,
) -> Dict[str, Any]:
    """Apply the complete workflow in memory and save only one final image."""
    idx, total = global_info
    original_size = os.path.getsize(input_path)

    if show_progress:
        render_progress(idx - 1, total, input_path, 5, 100, "Ouverture")
        time.sleep(0.01)

    with Image.open(input_path) as source_img:
        source_format = source_save_format_from_image(source_img)
        img = source_img.copy()

    resize_dimensions: Optional[Tuple[int, int]] = None

    if do_resize:
        if resize_config is None:
            raise ValueError("Configuration de redimensionnement manquante.")
        if show_progress:
            render_progress(idx - 1, total, input_path, 35, 100, "Resize")
            time.sleep(0.01)
        img, target_w, target_h = resize_pil_image(img, resize_config)
        resize_dimensions = (target_w, target_h)

    output_format = _determine_target_format(
        source_format=source_format,
        do_resize=do_resize,
        do_convert=do_convert,
        convert_config=convert_config,
        do_compress=do_compress,
        compress_config=compress_config,
    )

    output_path = _build_final_output_path(
        input_path=input_path,
        output_dir=output_dir,
        output_format=output_format,
        resize_dimensions=resize_dimensions,
        do_compress=do_compress,
        compress_config=compress_config,
    )

    if show_progress:
        render_progress(idx - 1, total, input_path, 60, 100, "Format")
        time.sleep(0.01)

    if do_compress:
        if compress_config is None:
            raise ValueError("Configuration de compression manquante.")

        # In master mode we must always produce the single final workflow file.
        # Therefore skip_if_larger is disabled only for this in-memory pipeline.
        master_compress_config = normalize_compress_config(compress_config)
        master_compress_config["skip_if_larger"] = False

        if show_progress:
            render_progress(idx - 1, total, input_path, 80, 100, "Compression")
            time.sleep(0.01)

        buffer = compress_pil_image_to_buffer(img, output_format, master_compress_config)
        with open(output_path, "wb") as handle:
            handle.write(buffer.getvalue())
    else:
        if show_progress:
            render_progress(idx - 1, total, input_path, 80, 100, "Sauvegarde")
            time.sleep(0.01)

        prepared = prepare_image_for_format(img, output_format)
        prepared.save(output_path, format=output_format, **save_params_for_format(output_format, prepared))

    new_size = os.path.getsize(output_path)

    if show_progress:
        render_progress(idx, total, input_path, 100, 100, "Termine")

    return {
        "status": "success",
        "input": input_path,
        "output": output_path,
        "original_size": original_size,
        "new_size": new_size,
        "format": output_format,
        "resize_dimensions": resize_dimensions,
    }


def process_workflow_images(
    files: List[str],
    output_dir: str,
    do_resize: bool,
    resize_config: Optional[Dict[str, Any]],
    do_convert: bool,
    convert_config: Optional[Dict[str, Any]],
    do_compress: bool,
    compress_config: Optional[Dict[str, Any]],
    show_progress: bool = True,
) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    results: List[Dict[str, Any]] = []
    output_files: List[str] = []
    errors: List[Dict[str, str]] = []
    total = len(files)

    for idx, input_path in enumerate(files, 1):
        try:
            result = process_workflow_image(
                input_path=input_path,
                output_dir=output_dir,
                do_resize=do_resize,
                resize_config=resize_config,
                do_convert=do_convert,
                convert_config=convert_config,
                do_compress=do_compress,
                compress_config=compress_config,
                global_info=(idx, total),
                show_progress=show_progress,
            )
            results.append(result)
            output_files.append(result["output"])
        except Exception as exc:
            errors.append({"file": input_path, "error": str(exc)})
            print(f"\n[Erreur] Workflow impossible pour {input_path}: {exc}")

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
    print_banner("master")

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

    print("\n--- CONFIGURATION DU WORKFLOW ---")
    print("Le master produit une seule image finale par image source.")
    print("Ordre du pipeline : redimensionnement -> conversion -> compression -> sauvegarde finale.")

    do_resize = ask_yes_no("Redimensionner ? (o/N) : ", default=False)
    do_convert = ask_yes_no("Convertir le format ? (o/N) : ", default=False)
    do_compress = ask_yes_no("Compresser ? (o/N) : ", default=False)

    if not any((do_resize, do_convert, do_compress)):
        print("Aucune operation selectionnee. Fin du programme.")
        sys.exit(0)

    try:
        resize_config = ask_resize_config() if do_resize else None
        convert_config = ask_convert_config() if do_convert else None
        # If conversion is already selected, the target extension must stay the
        # explicit conversion choice. We therefore do not ask the compressor to
        # convert to WebP in that case.
        compress_config = ask_compress_config(allow_webp_choice=not do_convert) if do_compress else None
    except ValueError as exc:
        print(f"[Erreur] {exc}")
        sys.exit(1)

    output_dir = ask_output_dir(
        paths=paths,
        files=files,
        default_folder_name="output_processed",
        batch_suffix="_MASTER",
    )

    print("\n--- RECAPITULATIF ---")
    print(f"Images source : {len(files)}")
    print(f"Sortie        : {output_dir}")
    print(f"Resize        : {'oui - ' + format_dimension_mode(resize_config) if resize_config else 'non'}")
    print(f"Conversion    : {'oui - ' + convert_config['format'] if convert_config else 'non'}")
    print(f"Compression   : {'oui - compress-' + compression_mode_label(compress_config) if compress_config else 'non'}")
    print("Nom final     : [nom]_[LxH]_compress-[mode].[extension] si resize + compression")

    if not ask_yes_no("Lancer le workflow ? (O/n) : ", default=True):
        print("Operation annulee.")
        sys.exit(0)

    start_time = time.time()

    try:
        result = process_workflow_images(
            files=files,
            output_dir=output_dir,
            do_resize=do_resize,
            resize_config=resize_config,
            do_convert=do_convert,
            convert_config=convert_config,
            do_compress=do_compress,
            compress_config=compress_config,
            show_progress=True,
        )
    except KeyboardInterrupt:
        print("\nInterruption utilisateur.")
        sys.exit(1)

    duration = time.time() - start_time
    diff = result["final_size"] - result["original_size"]

    print("\n" + "=" * 45)
    print("BILAN FINAL")
    print("=" * 45)
    print(f"Images traitees : {result['success_count']}/{len(files)}")
    print(f"Temps ecoule    : {duration:.2f} secondes")
    print(f"Taille initiale : {format_size(result['original_size'])}")
    print(f"Taille finale   : {format_size(result['final_size'])}")

    if diff < 0:
        percent = abs(diff) / result["original_size"] * 100 if result["original_size"] else 0
        print(f"Gain d'espace   : {format_size(abs(diff))} ({percent:.1f}%)")
    else:
        print(f"Augmentation    : {format_size(diff)}")

    if result["errors"]:
        print("\nErreurs :")
        for error in result["errors"]:
            print(f"- {error['file']}: {error['error']}")

    print(f"Sortie          : {output_dir}")
    print("=" * 45)
    print("SudSuite - Travail termine.")


if __name__ == "__main__":
    main()
