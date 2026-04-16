import os
import sys
import time
import io
import shutil
from datetime import datetime

# --- COMPATIBILITÉ WINDOWS ---
if sys.platform == "win32":
    os.system("")  # Active le support des codes ANSI/VT100
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

try:
    from PIL import Image
except ImportError:
    print("❌ La bibliothèque 'Pillow' n'est pas installée.")
    print("Veuillez l'installer avec la commande suivante :")
    print("   pip install Pillow")
    sys.exit(1)

# --- CONFIGURATION & CONSTANTES ---
VALID_EXTENSIONS = (".png", ".jpeg", ".jpg", ".webp", ".bmp", ".tiff")
RESIZE_METHODS = {
    "1": "Remplissage (Recadrage centré)",
    "2": "Adaptation (Bandes noires/transparentes)",
    "3": "Étirage (Peut déformer l'image)",
}


# --- UTILITAIRES ---
def format_size(size_in_bytes):
    """Formate une taille en octets vers une unité lisible."""
    for unit in ["O", "Ko", "Mo", "Go"]:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} To"


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
    target_files = []
    for path in paths:
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                # Smart Filtering
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
    return target_files


def render_progress(global_idx, global_total, filename, step=0, total_steps=100):
    """Affiche une barre de progression."""
    try:
        columns = shutil.get_terminal_size((80, 20)).columns
    except:
        columns = 80

    safety_margin = 15
    available_width = columns - safety_margin
    g_bar_len = 10
    l_bar_len = 10

    g_filled = int(g_bar_len * global_idx // global_total) if global_total > 0 else 0
    g_bar = "█" * g_filled + "░" * (g_bar_len - g_filled)
    g_pct = (global_idx / global_total * 100) if global_total > 0 else 0

    l_filled = int(l_bar_len * step // total_steps)
    l_bar = "━" * l_filled + " " * (l_bar_len - l_filled)

    fn = os.path.basename(filename)
    txt_space = available_width - 35
    if len(fn) > txt_space:
        fn = fn[: max(5, txt_space - 3)] + "..."

    line = f" G:[{g_bar}] {g_pct:>3.0f}% ({global_idx}/{global_total}) | D:[{l_bar}] | {fn}"
    sys.stdout.write("\r" + line.ljust(columns - 1))
    sys.stdout.flush()


# --- LOGIQUE DE REDIMENSIONNEMENT ---
def resize_image_fill(img, target_w, target_h):
    """Redimensionne et recadre l'image pour remplir les dimensions cibles (Center Crop)."""
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    target_ratio = target_w / target_h

    if src_ratio > target_ratio:
        # Source plus large que cible -> Redimensionner sur la hauteur
        new_h = target_h
        new_w = int(src_w * (target_h / src_h))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        # Recadrage central horizontal
        left = (new_w - target_w) // 2
        img = img.crop((left, 0, left + target_w, target_h))
    else:
        # Source plus haute que cible -> Redimensionner sur la largeur
        new_w = target_w
        new_h = int(src_h * (target_w / src_w))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        # Recadrage central vertical
        top = (new_h - target_h) // 2
        img = img.crop((0, top, target_w, top + target_h))

    return img


def resize_image_fit(img, target_w, target_h):
    """Redimensionne l'image pour qu'elle tienne dans les dimensions sans recadrage (Letterbox)."""
    img.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
    new_img = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    # Centrage
    offset = ((target_w - img.width) // 2, (target_h - img.height) // 2)
    new_img.paste(img, offset)
    return new_img


def resize_image_stretch(img, target_w, target_h):
    """Redimensionne en étirant (Déformation)."""
    return img.resize((target_w, target_h), Image.Resampling.LANCZOS)


def process_file(
    file_path,
    target_w,
    target_h,
    method_choice,
    output_dir,
    global_info,
    override_name=None,
):
    idx, total = global_info
    try:
        original_size = os.path.getsize(file_path)
        base_name = os.path.splitext(os.path.basename(file_path))[0]

        if override_name:
            output_filename = override_name
        else:
            # Auto-naming rules: YYYYMMDD_HHMMSS pour les lots
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"{base_name}_{target_w}x{target_h}_{timestamp}.png"

        output_path = os.path.join(output_dir, output_filename)

        img = Image.open(file_path)

        # Simulation progression
        for s in range(0, 51, 10):
            render_progress(idx - 1, total, file_path, step=s, total_steps=100)
            time.sleep(0.01)

        if method_choice == "1":
            img = resize_image_fill(img, target_w, target_h)
        elif method_choice == "2":
            img = resize_image_fit(img, target_w, target_h)
        else:
            img = resize_image_stretch(img, target_w, target_h)

        for s in range(60, 101, 10):
            render_progress(idx - 1, total, file_path, step=s, total_steps=100)
            time.sleep(0.01)

        # Preserve alpha if JPEG input but we save as PNG anyway
        img.save(output_path, "PNG", optimize=True)

        new_size = os.path.getsize(output_path)
        render_progress(idx, total, file_path, step=100, total_steps=100)
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

    print(f"✅ {len(files)} images détectées.")

    # 2. Dimensions
    try:
        print("\n--- 📏 DIMENSIONS CIBLES ---")
        w_input = input("Largeur : ").strip()
        if not w_input:
            raise ValueError
        target_w = int(w_input)

        h_input = input("Hauteur : ").strip()
        if not h_input:
            raise ValueError
        target_h = int(h_input)
    except ValueError:
        print("❌ Dimensions invalides. Veuillez entrer des nombres entiers.")
        sys.exit(1)

    # 3. Méthode
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
    success_count = 0
    total_original = 0
    total_new = 0

    start_time = time.time()
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
            )
            if res:
                success_count += 1
                total_original += orig
                total_new += new
        print()
    except KeyboardInterrupt:
        print("\n⚠️ Interruption utilisateur.")

    # 7. Bilan
    duration = time.time() - start_time
    print("\n" + "=" * 40)
    print("📊 BILAN FINAL")
    print("=" * 40)
    print(f"✅ Images traitées : {success_count}/{len(files)}")
    print(f"⏱️ Temps écoulé    : {duration:.2f} secondes")
    print(f"📦 Taille initiale : {format_size(total_original)}")
    print(f"📦 Taille finale   : {format_size(total_new)}")

    diff = total_new - total_original
    if diff < 0:
        print(f"📉 Gain d'espace   : {format_size(abs(diff))}")
    else:
        print(f"📈 Augmentation    : {format_size(diff)}")
    print("=" * 40)
    print("🚀 Fini !")


if __name__ == "__main__":
    main()
