import os
import sys
import time
import io
import shutil

# --- COMPATIBILITÉ WINDOWS ---
if sys.platform == "win32":
    os.system("")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

try:
    import fitz
except ImportError:
    print("❌ La bibliothèque 'PyMuPDF' (fitz) n'est pas installée.")
    print("Veuillez l'installer avec la commande suivante :")
    print("   pip install PyMuPDF")
    sys.exit(1)

try:
    from PIL import Image, ImageChops
except ImportError:
    print("❌ La bibliothèque 'Pillow' n'est pas installée.")
    print("Veuillez l'installer avec la commande suivante :")
    print("   pip install Pillow")
    sys.exit(1)

# --- CONFIGURATION & CONSTANTES ---
VALID_EXTENSIONS = (".pdf",)
SUPPORTED_OUTPUT_FORMATS = {
    "1": ("PNG", ".png"),
    "2": ("JPEG", ".jpg"),
}


# --- UTILITAIRES ---
def format_size(size_in_bytes):
    for unit in ["O", "Ko", "Mo", "Go"]:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} To"


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
    target_files = []
    for path in paths:
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                # Smart Filtering: ignorer les dossiers cachés ou système
                dirs[:] = [
                    d
                    for d in dirs
                    if not d.startswith((".", "__"))
                    and d not in ("node_modules", "dist", "build")
                ]
                for f in files:
                    if f.lower().endswith(VALID_EXTENSIONS):
                        target_files.append(os.path.join(root, f))
        elif os.path.isfile(path):
            if path.lower().endswith(VALID_EXTENSIONS):
                target_files.append(path)
            else:
                print(f"⚠️  Le fichier {os.path.basename(path)} n'est pas un PDF.")
        else:
            print(f"❌ {path} n'est ni un fichier ni un dossier valide.")
    return target_files


def render_progress(global_idx, global_total, filename, step=0, total_steps=100):
    """
    Affiche une barre de progression robuste sur une seule ligne.
    """
    try:
        columns = shutil.get_terminal_size((80, 20)).columns
    except:
        columns = 80

    safety_margin = 15
    available_width = columns - safety_margin
    g_bar_len = 10
    l_bar_len = 10

    g_filled = (
        int(g_bar_len * global_idx // global_total) if global_total > 0 else g_bar_len
    )
    g_bar = "█" * g_filled + "░" * (g_bar_len - g_filled)
    g_pct = (global_idx / global_total) * 100 if global_total > 0 else 100

    l_filled = int(l_bar_len * step // total_steps) if total_steps > 0 else l_bar_len
    l_bar = "━" * l_filled + " " * (l_bar_len - l_filled)

    fn = os.path.basename(filename)
    txt_space = available_width - 35
    if len(fn) > txt_space:
        fn = fn[: max(5, txt_space - 3)] + "..."

    line = f" G:[{g_bar}] {g_pct:>3.0f}% ({global_idx}/{global_total}) | D:[{l_bar}] | {fn}"
    sys.stdout.write("\r" + line.ljust(columns - 1))
    sys.stdout.flush()


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

            # Mise à jour de la barre de progression pour la page en cours
            step_pct = int((i / num_pages) * 100)
            render_progress(idx - 1, total, input_path, step=step_pct, total_steps=100)

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
            output_path = os.path.join(output_dir, page_filename)

            save_params = {}
            if target_format == "JPEG":
                save_params = {"quality": 95, "subsampling": 0}
            elif target_format == "PNG":
                save_params = {"optimize": True}

            img.save(output_path, format=target_format, **save_params)
            total_new_size += os.path.getsize(output_path)

        doc.close()

        # Progression à 100% pour ce fichier
        render_progress(idx, total, input_path, step=100, total_steps=100)

        return True, original_size, total_new_size
    except Exception as e:
        if not silent:
            print(f"\n❌ Erreur lors de la conversion de {input_path}: {e}")
        return False, 0, 0


def main():
    print_banner()

    paths = sys.argv[1:]
    if not paths:
        path_input = input("📂 Entrez le chemin du PDF ou du dossier : ").strip()
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
    first_arg = paths[0]
    if os.path.isdir(first_arg):
        output_dir = first_arg.rstrip("/\\") + "_images"
    else:
        output_dir = os.path.join(
            os.path.dirname(os.path.abspath(first_arg)), "pdf_images"
        )

    # 4. Confirmation
    print(f"\n📂 Dossier de sortie : {output_dir}")
    confirm = (
        input(
            f"⚠️  Les PDF seront convertis en {target_format} à {dpi} DPI. Continuer ? (O/n) : "
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
    success_count = 0
    total_original_size = 0
    total_new_size = 0
    total_files = len(files)

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
            )
            if res[0] is True:
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
    print(f"✅ PDF traités avec succès      : {success_count}/{total_files}")
    print(f"📦 Taille totale originale      : {format_size(total_original_size)}")
    print(f"📦 Taille totale images (Gén.)  : {format_size(total_new_size)}")

    variation = total_new_size - total_original_size
    if variation > 0:
        print(f"📈 Augmentation de taille       : {format_size(variation)}")
    else:
        print(f"📉 Gain d'espace                : {format_size(abs(variation))}")
    print("=" * 40)
    print("🚀 Travail terminé !")


if __name__ == "__main__":
    main()
