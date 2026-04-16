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
SUPPORTED_OUTPUT_FORMATS = {
    "1": ("PNG", ".png"),
    "2": ("JPEG", ".jpg"),
    "3": ("WEBP", ".webp"),
    "4": ("BMP", ".bmp"),
    "5": ("TIFF", ".tiff"),
    "6": ("GIF", ".gif"),
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
 ____            _  ____                          _   _                    
/ ___| _   _  __| |/ ___|___  _ ____   _____ _ __| |_(_)___ ___  ___  _ __ 
\___ \| | | |/ _` | |   / _ \| '_ \ \ / / _ \ '__| __| / __/ __|/ _ \| '__|
 ___) | |_| | (_| | |__| (_) | | | \ V /  __/ |  | |_| \__ \__ \ (_) | |   
|____/ \__,_|\__,_|\____\___/|_| |_|\_/ \___|_|   \__|_|___/___/\___/|_|   
    """
    print(banner)


def get_target_files(paths):
    """Collecte tous les fichiers images valides à partir des chemins fournis."""
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
                print(
                    f"⚠️  Le fichier {os.path.basename(path)} n'est pas une image supportée."
                )
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

    # Marge de sécurité pour éviter le wrapping (critique pour \r)
    # Les emojis comptent pour 1 en python mais 2 colonnes en visuel
    safety_margin = 15
    available_width = columns - safety_margin

    # Proportion des barres (plus petites pour la stabilité)
    g_bar_len = 10
    l_bar_len = 10

    # Barre Globale
    g_filled = int(g_bar_len * global_idx // global_total)
    g_bar = "█" * g_filled + "░" * (g_bar_len - g_filled)
    g_pct = (global_idx / global_total) * 100

    # Barre Locale
    l_filled = int(l_bar_len * step // total_steps)
    l_bar = "━" * l_filled + " " * (l_bar_len - l_filled)

    # Nom de fichier tronqué
    fn = os.path.basename(filename)
    # Calcul de l'espace pour le texte (on enlève les barres et préfixes)
    # "G:[###] 100% | L:[###] | " ~ 30 chars
    txt_space = available_width - 35
    if len(fn) > txt_space:
        fn = fn[: max(5, txt_space - 3)] + "..."

    # Ligne finale
    # On n'utilise pas d'emojis complexes ici pour garantir la largeur
    line = f" G:[{g_bar}] {g_pct:>3.0f}% ({global_idx}/{global_total}) | D:[{l_bar}] | {fn}"

    # Écriture propre
    sys.stdout.write("\r" + line.ljust(columns - 1))
    sys.stdout.flush()


def convert_image(
    input_path, target_format, target_ext, output_dir, silent=False, global_info=(0, 0)
):
    """Convertit une image unique ou l'ignore si elle existe déjà."""
    idx, total = global_info
    try:
        start_time = time.time()
        original_size = os.path.getsize(input_path)

        # Nom de fichier prévisible sans horodatage pour permettre l'idempotence
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        output_filename = f"{base_name}{target_ext}"
        output_path = os.path.join(output_dir, output_filename)

        # Vérification si déjà fait
        if os.path.exists(output_path):
            render_progress(idx, total, input_path, step=100, total_steps=100)
            return "skipped", 0, 0

        # Simulation de la progression par image
        for s in range(0, 101, 20):
            render_progress(idx - 1, total, input_path, step=s, total_steps=100)
            time.sleep(0.01)

        img = Image.open(input_path)

        # Gestion de la transparence
        if target_format == "JPEG" and img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        elif img.mode == "P" and target_format != "GIF":
            img = img.convert("RGBA" if "transparency" in img.info else "RGB")

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

    try:
        for i, f in enumerate(files, 1):
            res = convert_image(
                f,
                target_format,
                target_ext,
                output_dir,
                silent=True,
                global_info=(i, total_files),
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
