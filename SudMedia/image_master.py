import os
import sys

try:
    from .sudmedia_utils import (
        IMAGE_OUTPUT_FORMATS,
        Progress,
        ProcessingStats,
        RESIZE_METHODS,
        analyze_quality,
        collect_target_files,
        configure_console_output,
        configure_pillow,
        get_original_image_quality,
        image_save_options,
        prepare_image_for_quality,
        print_processing_summary,
        print_quality_analysis,
        reserve_output_path,
        resize_image,
    )
except ImportError:
    from sudmedia_utils import (
        IMAGE_OUTPUT_FORMATS,
        Progress,
        ProcessingStats,
        RESIZE_METHODS,
        analyze_quality,
        collect_target_files,
        configure_console_output,
        configure_pillow,
        get_original_image_quality,
        image_save_options,
        prepare_image_for_quality,
        print_processing_summary,
        print_quality_analysis,
        reserve_output_path,
        resize_image,
    )

configure_console_output()

try:
    from PIL import Image
    configure_pillow(Image)
except ImportError:
    print("❌ La bibliothèque 'Pillow' n'est pas installée.")
    print("Veuillez l'installer avec la commande suivante :")
    print("> pip install Pillow")
    sys.exit(1)

# --- CONFIGURATION & CONSTANTES ---
VALID_EXTENSIONS = (".png", ".jpeg", ".jpg", ".webp", ".bmp", ".tiff", ".gif")
SUPPORTED_OUTPUT_FORMATS = {
    key: value
    for key, value in IMAGE_OUTPUT_FORMATS.items()
    if value[0] != "GIF"
}


def print_banner():
    """Affiche le bandeau ASCII Art."""
    banner = r"""
 ____            _ __  __           _            
/ ___| _   _  __| |  \/  | __ _ ___| |_ ___ _ __ 
\___ \| | | |/ _` | |\/| |/ _` / __| __/ _ \ '__|
 ___) | |_| | (_| | |  | | (_| \__ \ ||  __/ |   
|____/ \__,_|\__,_|_|  |_|\__,_|___/\__\___|_|   
    """
    print(banner)


def main():
    print_banner()

    # 1. Chemins
    paths = []
    if len(sys.argv) > 1:
        paths = sys.argv[1:]
    else:
        path_input = (
            input("📂 Glissez un dossier ou fichier à traiter : ").strip().strip('"')
        )
        if path_input:
            paths = [path_input]

    if not paths:
        print("❌ Aucun chemin spécifié.")
        sys.exit(0)

    files = collect_target_files(
        paths,
        VALID_EXTENSIONS,
        item_label="une image supportée",
    )
    if not files:
        print("❌ Aucun fichier image valide trouvé.")
        sys.exit(0)

    print(f"✅ {len(files)} image(s) détectée(s).")
    if len(files) == 1:
        try:
            with Image.open(files[0]) as tmp_img:
                print(f"📐 Taille actuelle : {tmp_img.width} × {tmp_img.height} px")
        except Exception:
            pass

    # 2. Choix des opérations
    print("\n--- 🛠️ CONFIGURATION DU WORKFLOW ---")
    print("Quelles opérations voulez-vous effectuer ?")
    do_resize = input("📏 Redimensionner ? (o/N) : ").strip().lower() == "o"
    do_convert = input("🔄 Convertir le format ? (o/N) : ").strip().lower() == "o"
    do_compress = input("🗜️ Compresser ? (o/N) : ").strip().lower() == "o"

    if not any([do_resize, do_convert, do_compress]):
        print("⚠️ Aucune opération sélectionnée. Fin du programme.")
        sys.exit(0)

    # Config Resize
    resize_config = {}
    if do_resize:
        print("\n--- 📏 CONFIGURATION REDIMENSIONNEMENT ---")
        if files:
            print("📐 Dimensions d'origine (en pixels) :")
            if len(files) == 1:
                try:
                    with Image.open(files[0]) as tmp_img:
                        print(f"   • {os.path.basename(files[0])} : {tmp_img.width} × {tmp_img.height} px")
                except Exception:
                    pass
            elif len(files) <= 5:
                for f_item in files:
                    try:
                        with Image.open(f_item) as tmp_img:
                            print(f"   • {os.path.basename(f_item)} : {tmp_img.width} × {tmp_img.height} px")
                    except Exception:
                        pass
            else:
                try:
                    with Image.open(files[0]) as tmp_img:
                        print(f"   • Exemple (1ère image) : {tmp_img.width} × {tmp_img.height} px ({len(files)} images au total)")
                except Exception:
                    pass
        print("💡 Laissez une dimension vide (Entrée) pour un calcul automatique du ratio.")
        try:
            w_input = input("Largeur cible (laisser vide si auto) : ").strip()
            h_input = input("Hauteur cible (laisser vide si auto) : ").strip()

            target_w = int(w_input) if w_input else None
            target_h = int(h_input) if h_input else None

            if target_w is None and target_h is None:
                print("❌ Au moins une dimension (largeur ou hauteur) doit être spécifiée.")
                sys.exit(1)

            if (target_w is not None and target_w <= 0) or (target_h is not None and target_h <= 0):
                print("❌ Les dimensions doivent être supérieures à 0.")
                sys.exit(1)

            resize_config["w"] = target_w
            resize_config["h"] = target_h

            if target_w is not None and target_h is not None:
                print("Méthodes :")
                for k, v in RESIZE_METHODS.items():
                    print(f"  {k}. {v}")
                resize_config["method"] = input("Méthode (par défaut 1) : ").strip() or "1"
            else:
                resize_config["method"] = "auto"
        except ValueError:
            print("❌ Dimensions invalides. Veuillez saisir un nombre entier.")
            sys.exit(1)

    # Config Convert
    convert_config = {}
    if do_convert:
        print("\n--- 🔄 CONFIGURATION CONVERSION ---")
        for k, v in SUPPORTED_OUTPUT_FORMATS.items():
            print(f"  {k}. {v[0]}")
        choix = input("Format cible (numéro) : ").strip()
        if choix in SUPPORTED_OUTPUT_FORMATS:
            convert_config["format"], convert_config["ext"] = SUPPORTED_OUTPUT_FORMATS[
                choix
            ]
        else:
            print("❌ Format invalide.")
            sys.exit(1)

    # Config Compress
    compress_config = {}
    if do_compress:
        print("\n--- 🗜️ CONFIGURATION COMPRESSION ---")
        print("1. SANS PERTE (Optimisation)")
        print("2. AVEC PERTE (Réduction qualité)")
        mode = input("Mode (1 ou 2) : ").strip()
        if mode not in {"1", "2"}:
            print("❌ Mode de compression invalide.")
            sys.exit(1)
        compress_config["mode"] = mode
        if mode == "2":
            quality_analysis = analyze_quality(
                input("Qualité (1-100, ex: 75) : ").strip() or 75
            )
            compress_config["quality"] = quality_analysis.quality
            print_quality_analysis(quality_analysis)

    # 3. Dossier de sortie
    is_single_file = len(files) == 1
    if is_single_file:
        output_dir = os.path.dirname(os.path.abspath(files[0]))
    else:
        default_out = "output_processed"
        if os.path.isdir(paths[0]):
            default_out = paths[0].rstrip("/\\") + "_MASTER"

        output_dir = (
            input(f"\n📂 Dossier de sortie (par défaut: {default_out}) : ").strip()
            or default_out
        )
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    # 4. Traitement
    print("\n--- 🚀 TRAITEMENT EN COURS ---")
    stats = ProcessingStats(len(files))
    reserved_paths = set()
    progress = Progress(len(files), label="Image Master").start()

    try:
        for i, f_path in enumerate(files, 1):
            try:
                orig_size = os.path.getsize(f_path)

                # Image processing steps
                progress.update_item(i - 1, item=f_path, step=0, status="Ouverture")
                with Image.open(f_path) as source_image:
                    source_format = source_image.format or "PNG"
                    original_quality = get_original_image_quality(source_image)
                    img = source_image.copy()

                # Step 1: Resize
                if do_resize:
                    progress.update_item(i - 1, item=f_path, step=30, status="Redimensionnement")
                    img = resize_image(
                        img,
                        resize_config["w"],
                        resize_config["h"],
                        resize_config["method"],
                    )

                # Step 2 & 3: Convert & Compress (determined during save)
                progress.update_item(i - 1, item=f_path, step=70, status="Optimisation")

                # Determine Format
                save_fmt = source_format
                ext = os.path.splitext(f_path)[1]

                if do_convert:
                    save_fmt = convert_config["format"]
                    ext = convert_config["ext"]

                compression_mode = "standard"
                quality = 95
                if do_compress:
                    compression_mode = (
                        "lossless" if compress_config["mode"] == "1" else "lossy"
                    )
                    quality = compress_config.get("quality", 75)

                img = prepare_image_for_quality(
                    img,
                    save_fmt,
                    compression_mode=compression_mode,
                    quality=quality,
                )
                save_params = image_save_options(
                    save_fmt,
                    compression_mode=compression_mode,
                    quality=quality,
                    original_quality=original_quality,
                )

                # Output path
                base_name = os.path.splitext(os.path.basename(f_path))[0]

                suffix = ""
                if is_single_file:
                    if do_resize:
                        suffix += f"_{img.width}x{img.height}"
                    if do_compress:
                        suffix += "_min"
                    if not suffix and not do_convert:
                        suffix = "_new"

                out_path = os.path.join(output_dir, f"{base_name}{suffix}{ext}")
                out_path = reserve_output_path(out_path, reserved_paths)

                # Avoid collision if output is same as input
                if os.path.abspath(out_path) == os.path.abspath(f_path):
                    out_path = os.path.join(output_dir, f"{base_name}_final{ext}")

                img.save(out_path, format=save_fmt, **save_params)

                stats.add_success(orig_size, os.path.getsize(out_path))
                progress.complete_file(item=f_path, status="Terminé")

            except Exception as e:
                stats.add_error()
                progress.complete_file(item=f_path, status="Erreur")
                print(f"\n❌ Erreur sur {os.path.basename(f_path)}: {e}")

        progress.finish()
    except KeyboardInterrupt:
        progress.abort()
        print("\n\n⚠️ Interruption utilisateur.")

    # 5. Bilan
    print_processing_summary(
        stats,
        title="BILAN FINAL",
        item_label="Images traitées",
        output_path=output_dir,
        width=45,
    )
    print("🚀 SudSuite - Travail terminé !")


if __name__ == "__main__":
    main()
