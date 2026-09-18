import os
import sys
from datetime import datetime

try:
    from .sudmedia_utils import (
        Progress,
        ProcessingStats,
        RESIZE_METHODS,
        collect_target_files,
        configure_console_output,
        configure_pillow,
        print_processing_summary,
        reserve_output_path,
        resize_image,
    )
except ImportError:
    from sudmedia_utils import (
        Progress,
        ProcessingStats,
        RESIZE_METHODS,
        collect_target_files,
        configure_console_output,
        configure_pillow,
        print_processing_summary,
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
    print("   pip install Pillow")
    sys.exit(1)

# --- CONFIGURATION & CONSTANTES ---
VALID_EXTENSIONS = (".png", ".jpeg", ".jpg", ".webp", ".bmp", ".tiff")
def print_banner():
    """Affiche le bandeau ASCII Art."""
    banner = r"""
 ____            _ ____           _              
/ ___| _   _  __| |  _ \ ___  ___(_)_______ _ __ 
\___ \| | | |/ _` | |_) / _ \/ __| |_  / _ \ '__|
 ___) | |_| | (_| |  _ <  __/\__ \ |/ /  __/ |   
|____/ \__,_|\__,_|_| \_\___||___/_/___\___|_|   
    """
    print(banner)


def get_target_files(paths):
    """Collecte tous les fichiers images valides à partir des chemins fournis."""
    return collect_target_files(
        paths,
        VALID_EXTENSIONS,
        item_label="une image supportée",
    )


def process_file(
    file_path,
    target_w,
    target_h,
    method_choice,
    output_dir,
    global_info,
    override_name=None,
    reserved_paths=None,
    progress=None,
):
    idx, total = global_info
    try:
        original_size = os.path.getsize(file_path)
        base_name = os.path.splitext(os.path.basename(file_path))[0]

        with Image.open(file_path) as source_image:
            img = source_image.copy()

        if progress:
            progress.set_item(file_path, "Redimensionnement")
        img = resize_image(img, target_w, target_h, method_choice)

        if override_name:
            output_filename = override_name
        else:
            # Auto-naming rules: YYYYMMDD_HHMMSS pour les lots
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"{base_name}_{img.width}x{img.height}_{timestamp}.png"

        output_path = reserve_output_path(
            os.path.join(output_dir, output_filename),
            reserved_paths,
        )

        # Preserve alpha if JPEG input but we save as PNG anyway
        if progress:
            progress.set_item(file_path, "Sauvegarde")
        img.save(output_path, "PNG", optimize=True)

        new_size = os.path.getsize(output_path)
        return True, original_size, new_size
    except Exception as e:
        print(f"\n❌ Erreur sur {file_path}: {e}")
        return False, 0, 0


def main():
    print_banner()

    # 1. Entrée des fichiers
    paths = []
    if len(sys.argv) > 1:
        paths = sys.argv[1:]
    else:
        path_input = (
            input("📂 Glissez un fichier ou un dossier (ou entrez le chemin) : ")
            .strip()
            .strip('"')
        )
        if path_input:
            paths = [path_input]

    if not paths:
        print("❌ Aucun chemin spécifié.")
        sys.exit(0)

    files = get_target_files(paths)
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

    # 2. Dimensions
    try:
        print("\n--- 📏 DIMENSIONS CIBLES ---")
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
        w_input = input("Largeur (laisser vide si auto) : ").strip()
        h_input = input("Hauteur (laisser vide si auto) : ").strip()

        target_w = int(w_input) if w_input else None
        target_h = int(h_input) if h_input else None

        if target_w is None and target_h is None:
            print("❌ Au moins une dimension (largeur ou hauteur) doit être spécifiée.")
            sys.exit(1)

        if (target_w is not None and target_w <= 0) or (target_h is not None and target_h <= 0):
            print("❌ Les dimensions doivent être supérieures à 0.")
            sys.exit(1)
    except ValueError:
        print("❌ Dimensions invalides. Veuillez entrer des nombres entiers.")
        sys.exit(1)

    # 3. Méthode
    method_choice = "1"
    if target_w is not None and target_h is not None:
        print("\n--- ⚙️ MÉTHODE DE REDIMENSIONNEMENT ---")
        for k, v in RESIZE_METHODS.items():
            print(f"{k}. {v}")
        method_choice = input("Votre choix (par défaut 1) : ").strip() or "1"
        if method_choice not in RESIZE_METHODS:
            print("⚠️ Choix invalide, utilisation de 'Remplissage'.")
            method_choice = "1"

    # 4. Dossier de sortie
    first_arg = paths[0]
    is_single_file = len(files) == 1

    if is_single_file:
        output_dir = os.path.dirname(os.path.abspath(files[0]))
        output_msg = f"L'image sera sauvegardée dans : {output_dir}"
    elif os.path.isdir(first_arg):
        output_dir = first_arg.rstrip("/\\") + "_resized"
        output_msg = f"Dossier de sortie : {output_dir}"
    else:
        output_dir = os.path.join(
            os.path.dirname(os.path.abspath(first_arg)), "resized"
        )
        output_msg = f"Dossier de sortie : {output_dir}"

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    print(f"\n📂 {output_msg}")

    # 5. Confirmation
    confirm = input(f"🚀 Prêt à traiter {len(files)} images ? (O/n) : ").strip().lower()
    if confirm == "n":
        print("🚫 Opération annulée.")
        sys.exit(0)

    # 6. Traitement
    print("\n--- 🚀 TRAITEMENT ---")
    stats = ProcessingStats(len(files))
    reserved_paths = set()
    progress = Progress(len(files), label="Redimensionnement").start()

    try:
        for i, f in enumerate(files, 1):
            override_name = None
            if is_single_file:
                base = os.path.splitext(os.path.basename(f))[0]
                override_name = f"{base}_resized.png"

            res, orig, new = process_file(
                f,
                target_w,
                target_h,
                method_choice,
                output_dir,
                (i, len(files)),
                override_name,
                reserved_paths,
                progress,
            )
            if res:
                stats.add_success(orig, new)
                progress.complete_file(item=f, status="Redimensionné")
            else:
                stats.add_error()
                progress.complete_file(item=f, status="Erreur")
        progress.finish()
    except KeyboardInterrupt:
        progress.abort()
        print("\n⚠️ Interruption utilisateur.")

    # 7. Bilan
    print_processing_summary(
        stats,
        title="BILAN FINAL",
        item_label="Images redimensionnées",
        output_path=output_dir,
        width=40,
    )
    print("🚀 Fini !")


if __name__ == "__main__":
    main()
