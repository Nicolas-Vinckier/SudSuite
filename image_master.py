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
VALID_EXTENSIONS = (".png", ".jpeg", ".jpg", ".webp", ".bmp", ".tiff", ".gif")
RESIZE_METHODS = {
    "1": "Remplissage (Recadrage centré)",
    "2": "Adaptation (Bandes noires/transparentes)",
    "3": "Étirage (Peut déformer l'image)",
}
SUPPORTED_OUTPUT_FORMATS = {
    "1": ("PNG", ".png"),
    "2": ("JPEG", ".jpg"),
    "3": ("WEBP", ".webp"),
    "4": ("BMP", ".bmp"),
    "5": ("TIFF", ".tiff"),
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
 ____            _  __  __           _             
/ ___| _   _  __| ||  \/  | __ _ ___| |_ ___ _ __  
\___ \| | | |/ _` || |\/| |/ _` / __| __/ _ \ '__| 
 ___) | |_| | (_| || |  | | (_| \__ \ ||  __/ |    
|____/ \__,_|\__,_||_|  |_|\__,_|___/\__\___|_|    
    """
    print(banner)


def get_target_files(paths):
    """Collecte tous les fichiers images valides à partir des chemins fournis."""
    target_files = []
    for path in paths:
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if not d.startswith((".", "__")) and d not in ("node_modules", "dist", "build")]
                for f in files:
                    if f.lower().endswith(VALID_EXTENSIONS):
                        target_files.append(os.path.join(root, f))
        elif os.path.isfile(path):
            if path.lower().endswith(VALID_EXTENSIONS):
                target_files.append(path)
    return target_files


def render_progress(global_idx, global_total, filename, step=0, total_steps=100, status=""):
    """Barre de progression sur une seule ligne."""
    try:
        columns = shutil.get_terminal_size((80, 20)).columns
    except:
        columns = 80

    safety_margin = 15
    available_width = columns - safety_margin
    g_bar_len = 10
    l_bar_len = 8

    g_filled = int(g_bar_len * global_idx // global_total) if global_total > 0 else 0
    g_bar = "█" * g_filled + "░" * (g_bar_len - g_filled)
    g_pct = (global_idx / global_total * 100) if global_total > 0 else 0

    l_filled = int(l_bar_len * step // total_steps)
    l_bar = "━" * l_filled + " " * (l_bar_len - l_filled)

    fn = os.path.basename(filename)
    txt_space = available_width - 45
    if len(fn) > txt_space:
        fn = fn[: max(5, txt_space - 3)] + "..."

    line = f" G:[{g_bar}] {g_pct:>3.0f}% | {status:<10} | [{l_bar}] | {fn}"
    sys.stdout.write("\r" + line.ljust(columns - 1))
    sys.stdout.flush()


# --- LOGIQUE DE REDIMENSIONNEMENT ---
def resize_image(img, target_w, target_h, method):
    if method == "1": # Fill / Center Crop
        src_w, src_h = img.size
        src_ratio = src_w / src_h
        target_ratio = target_w / target_h
        if src_ratio > target_ratio:
            new_h = target_h
            new_w = int(src_w * (target_h / src_h))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left = (new_w - target_w) // 2
            img = img.crop((left, 0, left + target_w, target_h))
        else:
            new_w = target_w
            new_h = int(src_h * (target_w / src_w))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            top = (new_h - target_h) // 2
            img = img.crop((0, top, target_w, top + target_h))
    elif method == "2": # Fit / Letterbox
        img.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
        new_img = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        offset = ((target_w - img.width) // 2, (target_h - img.height) // 2)
        new_img.paste(img, offset)
        img = new_img
    else: # Stretch
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    return img


def main():
    print_banner()

    # 1. Chemins
    paths = []
    if len(sys.argv) > 1:
        paths = sys.argv[1:]
    else:
        path_input = input("📂 Glissez un dossier ou fichier à traiter : ").strip().strip('"')
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
        try:
            resize_config['w'] = int(input("Largeur cible : ").strip())
            resize_config['h'] = int(input("Hauteur cible : ").strip())
            print("Méthodes :")
            for k, v in RESIZE_METHODS.items(): print(f"  {k}. {v}")
            resize_config['method'] = input("Méthode (par défaut 1) : ").strip() or "1"
        except ValueError:
            print("❌ Dimensions invalides.")
            sys.exit(1)

    # Config Convert
    convert_config = {}
    if do_convert:
        print("\n--- 🔄 CONFIGURATION CONVERSION ---")
        for k, v in SUPPORTED_OUTPUT_FORMATS.items(): print(f"  {k}. {v[0]}")
        choix = input("Format cible (numéro) : ").strip()
        if choix in SUPPORTED_OUTPUT_FORMATS:
            convert_config['format'], convert_config['ext'] = SUPPORTED_OUTPUT_FORMATS[choix]
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
        compress_config['mode'] = mode
        if mode == "2":
            compress_config['quality'] = int(input("Qualité (1-100, ex: 75) : ").strip() or "75")

    # 3. Dossier de sortie
    is_single_file = len(files) == 1
    if is_single_file:
        output_dir = os.path.dirname(os.path.abspath(files[0]))
    else:
        default_out = "output_processed"
        if os.path.isdir(paths[0]):
            default_out = paths[0].rstrip("/\\") + "_MASTER"
        
        output_dir = input(f"\n📂 Dossier de sortie (par défaut: {default_out}) : ").strip() or default_out
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    # 4. Traitement
    print("\n--- 🚀 TRAITEMENT EN COURS ---")
    start_time = time.time()
    success_count = 0
    total_orig_size = 0
    total_final_size = 0

    try:
        for i, f_path in enumerate(files, 1):
            try:
                orig_size = os.path.getsize(f_path)
                total_orig_size += orig_size
                
                # Image processing steps
                render_progress(i-1, len(files), f_path, 0, 100, "Ouverture")
                img = Image.open(f_path)
                
                # Step 1: Resize
                if do_resize:
                    render_progress(i-1, len(files), f_path, 30, 100, "Resize")
                    img = resize_image(img, resize_config['w'], resize_config['h'], resize_config['method'])
                
                # Step 2 & 3: Convert & Compress (determined during save)
                render_progress(i-1, len(files), f_path, 70, 100, "Optimisation")
                
                # Determine Format
                save_fmt = img.format if img.format else "PNG"
                ext = os.path.splitext(f_path)[1]
                
                if do_convert:
                    save_fmt = convert_config['format']
                    ext = convert_config['ext']
                
                # Handling JPEG transparency
                if save_fmt == "JPEG" and img.mode in ("RGBA", "P", "LA"):
                    img = img.convert("RGB")
                
                # Prepare save params
                save_params = {"optimize": True}
                if do_compress:
                    if compress_config['mode'] == "1": # Lossless
                        if save_fmt == "WEBP": save_params["lossless"] = True
                        if save_fmt == "JPEG": save_params["quality"] = "keep"
                    else: # Lossy
                        save_params["quality"] = compress_config.get('quality', 75)

                # Output path
                base_name = os.path.splitext(os.path.basename(f_path))[0]
                
                suffix = ""
                if is_single_file:
                    if do_resize:
                        suffix += f"_{resize_config['w']}x{resize_config['h']}"
                    if do_compress:
                        suffix += "_min"
                    if not suffix and not do_convert:
                        suffix = "_new"
                
                out_path = os.path.join(output_dir, f"{base_name}{suffix}{ext}")
                
                # Avoid collision if output is same as input
                if os.path.abspath(out_path) == os.path.abspath(f_path):
                    out_path = os.path.join(output_dir, f"{base_name}_final{ext}")

                img.save(out_path, format=save_fmt, **save_params)
                
                total_final_size += os.path.getsize(out_path)
                success_count += 1
                render_progress(i, len(files), f_path, 100, 100, "Terminé")
                
            except Exception as e:
                print(f"\n❌ Erreur sur {os.path.basename(f_path)}: {e}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Interruption utilisateur.")

    # 5. Bilan
    duration = time.time() - start_time
    print("\n\n" + "=" * 45)
    print("📊 BILAN FINAL")
    print("=" * 45)
    print(f"✅ Images traitées : {success_count}/{len(files)}")
    print(f"⏱️ Temps écoulé    : {duration:.2f} secondes")
    print(f"📦 Taille initiale : {format_size(total_orig_size)}")
    print(f"📦 Taille finale   : {format_size(total_final_size)}")
    
    diff = total_final_size - total_orig_size
    if diff < 0:
        print(f"📉 Gain d'espace   : {format_size(abs(diff))} ({abs(diff)/total_orig_size*100:.1f}%)")
    else:
        print(f"📈 Augmentation    : {format_size(diff)}")
    print(f"📂 Sortie          : {output_dir}")
    print("=" * 45)
    print("🚀 SudSuite - Travail terminé !")

if __name__ == "__main__":
    main()
