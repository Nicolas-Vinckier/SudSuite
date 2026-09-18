import os
import sys

try:
    from .sudmedia_utils import (
        IMAGE_OUTPUT_FORMATS,
        Progress,
        ProcessingStats,
        collect_target_files,
        configure_console_output,
        configure_pillow,
        image_save_options,
        print_processing_summary,
        reserve_output_path,
    )
except ImportError:
    from sudmedia_utils import (
        IMAGE_OUTPUT_FORMATS,
        Progress,
        ProcessingStats,
        collect_target_files,
        configure_console_output,
        configure_pillow,
        image_save_options,
        print_processing_summary,
        reserve_output_path,
    )

configure_console_output()

try:
    import pymupdf as fitz
except ImportError:
    try:
        # Compatibilité avec les versions historiques de PyMuPDF.
        import fitz
    except ImportError:
        print("❌ La bibliothèque 'PyMuPDF' n'est pas installée.")
        print("Veuillez l'installer avec la commande suivante :")
        print("   pip install PyMuPDF")
        sys.exit(1)

try:
    from PIL import Image, ImageChops
    configure_pillow(Image)
except ImportError:
    print("❌ La bibliothèque 'Pillow' n'est pas installée.")
    print("Veuillez l'installer avec la commande suivante :")
    print("   pip install Pillow")
    sys.exit(1)

# --- CONFIGURATION & CONSTANTES ---
VALID_EXTENSIONS = (".pdf",)
SUPPORTED_OUTPUT_FORMATS = {
    key: IMAGE_OUTPUT_FORMATS[key]
    for key in ("1", "2")
}


def print_banner():
    banner = r"""
 ____            _ ____  ____  _____ ____  ___                 
/ ___| _   _  __| |  _ \|  _ \|  ___|___ \|_ _|_ __ ___   __ _ 
\___ \| | | |/ _` | |_) | | | | |_    __) || || '_ ` _ \ / _` |
 ___) | |_| | (_| |  __/| |_| |  _|  / __/ | || | | | | | (_| |
|____/ \__,_|\__,_|_|   |____/|_|   |_____|___|_| |_| |_|\__, |
                                                         |___/ 
    """
    print(banner)


def get_target_files(paths):
    return collect_target_files(
        paths,
        VALID_EXTENSIONS,
        item_label="un PDF",
    )


def crop_white_borders(img, padding=10):
    """
    Recadre l'image pour retirer les bordures blanches autour du contenu.
    """
    # Créer une image blanche de la même taille
    bg = Image.new(img.mode, img.size, (255, 255, 255))
    # Trouver la différence
    diff = ImageChops.difference(img, bg)
    # Augmenter le contraste de la différence pour ignorer les petits artéfacts
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        left, upper, right, lower = bbox
        # Ajouter du padding pour ne pas couper au pixel près
        left = max(0, left - padding)
        upper = max(0, upper - padding)
        right = min(img.width, right + padding)
        lower = min(img.height, lower + padding)
        return img.crop((left, upper, right, lower))
    return img


def convert_pdf(
    input_path,
    target_format,
    target_ext,
    output_dir,
    dpi=150,
    auto_crop=False,
    silent=False,
    global_info=(0, 0),
    reserved_paths=None,
    progress=None,
):
    """Convertit un PDF en une ou plusieurs images."""
    idx, total = global_info
    try:
        original_size = os.path.getsize(input_path)
        base_name = os.path.splitext(os.path.basename(input_path))[0]

        doc = fitz.open(input_path)
        num_pages = len(doc)
        total_new_size = 0

        # Le multiplicateur dépend du DPI souhaité (PyMuPDF utilise 72 DPI par défaut)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        for i in range(num_pages):
            page = doc.load_page(i)

            if progress:
                progress.update_item(
                    idx - 1,
                    item=input_path,
                    step=i,
                    total_steps=max(1, num_pages),
                    status=f"Page {i + 1}/{num_pages}",
                )

            # Rendu de la page
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # Conversion vers Pillow Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Redimensionnement sur le contenu si demandé
            if auto_crop:
                img = crop_white_borders(img)

            # Gestion du nom de fichier : s'il y a plusieurs pages, on ajoute le numéro
            page_filename = (
                f"{base_name}_page_{i+1}{target_ext}"
                if num_pages > 1
                else f"{base_name}{target_ext}"
            )
            output_path = reserve_output_path(
                os.path.join(output_dir, page_filename),
                reserved_paths,
            )

            save_params = image_save_options(target_format, quality=95)

            img.save(output_path, format=target_format, **save_params)
            total_new_size += os.path.getsize(output_path)

        doc.close()

        return True, original_size, total_new_size
    except Exception as e:
        if not silent:
            print(f"\n❌ Erreur lors de la conversion de {input_path}: {e}")
        return False, 0, 0


def main():
    print_banner()

    paths = [p.strip('"\' ') for p in sys.argv[1:] if p.strip('"\' ')]
    if not paths:
        path_input = input("📂 Entrez le chemin du PDF ou du dossier : ").strip().strip('"\' ')
        if not path_input:
            print("❌ Aucun chemin fourni. Arrêt.")
            sys.exit(0)
        paths = [path_input]

    # 1. Collecte des fichiers
    print("🔍 Analyse des fichiers...")
    files = get_target_files(paths)

    if not files:
        print("❌ Aucun fichier PDF trouvé.")
        sys.exit(1)

    if len(files) == 1:
        print(f"🚀 1 fichier PDF détecté : {os.path.basename(files[0])}")
    else:
        print(f"🚀 {len(files)} PDF détecté(s).")

    # 2. Paramètres
    print("\n--- 🎯 PARAMÈTRES DE CONVERSION ---")

    dpi_input = input(
        "Qualité (DPI) souhaitée (ex: 150 = Standard, 300 = Haute Qualité) [150 par défaut] : "
    ).strip()
    dpi = int(dpi_input) if dpi_input.isdigit() else 150

    crop_input = (
        input(
            "Voulez-vous recadrer automatiquement le blanc autour du contenu ? (o/N) : "
        )
        .strip()
        .lower()
    )
    auto_crop = crop_input == "o"

    for k, v in SUPPORTED_OUTPUT_FORMATS.items():
        print(f"{k}. {v[0]}")
    choix = input(
        "Choisissez le format d'image cible (numéro) [1 par défaut] : "
    ).strip()
    if not choix:
        choix = "1"

    if choix not in SUPPORTED_OUTPUT_FORMATS:
        print("❌ Choix invalide.")
        sys.exit(1)

    target_format, target_ext = SUPPORTED_OUTPUT_FORMATS[choix]

    # 3. Détermination du dossier de sortie
    first_path = paths[0]
    if os.path.isfile(first_path):
        file_basename_no_ext = os.path.splitext(os.path.basename(first_path))[0]
        default_output_dir = os.path.join(
            os.path.dirname(os.path.abspath(first_path)),
            f"{file_basename_no_ext}_images",
        )
    elif os.path.isdir(first_path):
        default_output_dir = first_path.rstrip("/\\") + "_images"
    else:
        default_output_dir = os.path.join(
            os.path.dirname(os.path.abspath(files[0])), "pdf_images"
        )

    out_dir_input = (
        input(f"📂 Dossier de sortie [{default_output_dir}] : ")
        .strip()
        .strip('"\' ')
    )
    output_dir = out_dir_input if out_dir_input else default_output_dir

    # 4. Confirmation
    print(f"\n📂 Dossier de sortie retenu : {output_dir}")
    confirm = (
        input(
            f"⚠️  Les PDF ({len(files)} fichier(s)) seront convertis en {target_format} à {dpi} DPI. Continuer ? (O/n) : "
        )
        .strip()
        .lower()
    )
    if confirm == "n":
        print("🚫 Opération annulée.")
        sys.exit(0)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 5. Traitement
    print("\n--- ⚙️ TRAITEMENT EN COURS ---")
    total_files = len(files)
    stats = ProcessingStats(total_files)
    reserved_paths = set()
    progress = Progress(total_files, label="PDF vers image").start()

    try:
        for i, f in enumerate(files, 1):
            res = convert_pdf(
                f,
                target_format,
                target_ext,
                output_dir,
                dpi=dpi,
                auto_crop=auto_crop,
                silent=True,
                global_info=(i, total_files),
                reserved_paths=reserved_paths,
                progress=progress,
            )
            if res[0] is True:
                stats.add_success(res[1], res[2])
                progress.complete_file(item=f, status="Converti")
            else:
                stats.add_error()
                progress.complete_file(item=f, status="Erreur")
        progress.finish()
    except KeyboardInterrupt:
        progress.abort()
        print("\n\n⚠️  Interruption par l'utilisateur. Arrêt du traitement...")

    # 6. Bilan
    print_processing_summary(
        stats,
        item_label="PDF convertis",
        original_label="Taille des PDF",
        final_label="Taille des images",
        output_path=output_dir,
        width=40,
    )
    print("🚀 Travail terminé !")


if __name__ == "__main__":
    main()
