import os
import sys
import time

try:
    from .sudmedia_utils import (
        IMAGE_OUTPUT_FORMATS,
        collect_target_files,
        configure_console_output,
        configure_pillow,
        format_size,
        prepare_image_for_format,
        render_progress,
        reserve_output_path,
    )
except ImportError:
    from sudmedia_utils import (
        IMAGE_OUTPUT_FORMATS,
        collect_target_files,
        configure_console_output,
        configure_pillow,
        format_size,
        prepare_image_for_format,
        render_progress,
        reserve_output_path,
    )

configure_console_output()

try:
    from PIL import Image
    configure_pillow(Image)
except ImportError:
    print("❌ La bibliothèque 'Pillow' n'est pas installée.")
    print("Veuillez l'installer avec la commande suivante :")
    print("   pip install Pillow")
    sys.exit(1)

# --- CONFIGURATION & CONSTANTES ---
VALID_EXTENSIONS = (".png", ".jpeg", ".jpg", ".webp", ".bmp", ".tiff", ".gif")
SUPPORTED_OUTPUT_FORMATS = IMAGE_OUTPUT_FORMATS.copy()


def print_banner():
    """Affiche le bandeau ASCII Art."""
    banner = r"""
 ____            _  ____                          _   _                    
/ ___| _   _  __| |/ ___|___  _ ____   _____ _ __| |_(_)___ ___  ___  _ __ 
\___ \| | | |/ _` | |   / _ \| '_ \ \ / / _ \ '__| __| / __/ __|/ _ \| '__|
 ___) | |_| | (_| | |__| (_) | | | \ V /  __/ |  | |_| \__ \__ \ (_) | |   
|____/ \__,_|\__,_|\____\___/|_| |_|\_/ \___|_|   \__|_|___/___/\___/|_|   
    """
    print(banner)


def get_target_files(paths):
    """Collecte tous les fichiers images valides à partir des chemins fournis."""
    return collect_target_files(
        paths,
        VALID_EXTENSIONS,
        item_label="une image supportée",
    )


def convert_image(
    input_path,
    target_format,
    target_ext,
    output_dir,
    silent=False,
    global_info=(0, 0),
    reserved_paths=None,
):
    """Convertit une image unique ou l'ignore si elle existe déjà."""
    idx, total = global_info
    try:
        original_size = os.path.getsize(input_path)

        # Nom de fichier prévisible sans horodatage pour permettre l'idempotence
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        output_filename = f"{base_name}{target_ext}"
        output_path = reserve_output_path(
            os.path.join(output_dir, output_filename),
            reserved_paths,
        )

        # Vérification si déjà fait
        if os.path.exists(output_path):
            render_progress(idx, total, input_path, step=100, total_steps=100)
            return "skipped", 0, 0

        # Simulation de la progression par image
        for s in range(0, 101, 20):
            render_progress(idx - 1, total, input_path, step=s, total_steps=100)
            time.sleep(0.01)

        img = Image.open(input_path)

        img = prepare_image_for_format(img, target_format)

        # Sauvegarde
        save_params = {}
        if target_format == "WEBP":
            save_params = {"lossless": True, "quality": 100}
        elif target_format == "JPEG":
            save_params = {"quality": 100, "subsampling": 0}
        elif target_format == "PNG":
            save_params = {"optimize": True}

        img.save(output_path, format=target_format, **save_params)

        render_progress(idx, total, input_path, step=100, total_steps=100)

        new_size = os.path.getsize(output_path)
        return True, original_size, new_size
    except Exception as e:
        if not silent:
            print(f"\n❌ Erreur lors de la conversion de {input_path}: {e}")
        return False, 0, 0


def main():
    print_banner()

    if len(sys.argv) < 2:
        print(
            "📂 Utilisation : python image_convertissor.py <image_ou_dossier_1> [image_ou_dossier_2] ..."
        )
        sys.exit(0)

    # 1. Collecte des fichiers
    print("🔍 Analyse des fichiers...")
    files = get_target_files(sys.argv[1:])

    if not files:
        print("❌ Aucun fichier image trouvé.")
        sys.exit(1)

    print(f"🚀 {len(files)} images détectées.")

    # 2. Sélection du format cible
    print("\n--- 🎯 SÉLECTION DU FORMAT CIBLE ---")
    for k, v in SUPPORTED_OUTPUT_FORMATS.items():
        print(f"{k}. {v[0]}")

    choix = input("\nChoisissez le format cible (numéro) : ").strip()
    if choix not in SUPPORTED_OUTPUT_FORMATS:
        print("❌ Choix invalide.")
        sys.exit(1)

    target_format, target_ext = SUPPORTED_OUTPUT_FORMATS[choix]

    # 3. Détermination du dossier de sortie
    first_arg = sys.argv[1]
    if os.path.isdir(first_arg):
        output_dir = first_arg.rstrip("/\\") + "_convert"
    else:
        output_dir = os.path.join(
            os.path.dirname(os.path.abspath(first_arg)), "converted"
        )

    # 4. Confirmation
    print(f"\n📂 Dossier de sortie : {output_dir}")
    confirm = (
        input(
            f"⚠️  Les images seront converties en {target_format}. Continuer ? (O/n) : "
        )
        .strip()
        .lower()
    )
    if confirm == "n":
        print("🚫 Opération annulée.")
        sys.exit(0)

    # Création du dossier si besoin
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 5. Traitement
    print("\n--- ⚙️ TRAITEMENT EN COURS ---")
    success_count = 0
    skipped_count = 0
    total_original_size = 0
    total_new_size = 0
    total_files = len(files)
    reserved_paths = set()

    try:
        for i, f in enumerate(files, 1):
            res = convert_image(
                f,
                target_format,
                target_ext,
                output_dir,
                silent=True,
                global_info=(i, total_files),
                reserved_paths=reserved_paths,
            )
            if res == "skipped":
                skipped_count += 1
            elif res[0] is True:
                success_count += 1
                total_original_size += res[1]
                total_new_size += res[2]

        # On saute une ligne après les barres de chargement
        print()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interruption par l'utilisateur. Arrêt du traitement...")

    # 6. Bilan
    print("\n" + "=" * 40)
    print("📊 BILAN DE L'OPÉRATION")
    print("=" * 40)
    print(f"✅ Images traitées avec succès : {success_count}/{total_files}")
    if skipped_count > 0:
        print(f"⏩ Images déjà présentes (ignorées) : {skipped_count}")
    print(f"📦 Taille totale originale     : {format_size(total_original_size)}")
    print(f"📦 Taille totale convertie      : {format_size(total_new_size)}")

    variation = total_new_size - total_original_size
    if variation > 0:
        print(f"📈 Augmentation de taille      : {format_size(variation)}")
    else:
        print(f"📉 Gain d'espace               : {format_size(abs(variation))}")
    print("=" * 40)
    print("🚀 Travail terminé !")


if __name__ == "__main__":
    main()
