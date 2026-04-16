import os
import zipfile
import tarfile
import time
import datetime
import sys
from pathlib import Path

# --- CONFIGURATION ---
EXCLUDE_PATTERNS = sorted({
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    ".vscode",
    ".idea",
    ".DS_Store",
    "Thumbs.db",
    "venv",
    ".next",
})


def format_size(size_in_bytes):
    for unit in ["O", "Ko", "Mo", "Go"]:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} To"


def get_folder_size(folder_path):
    total_size = 0
    file_count = 0
    for root, dirs, files in os.walk(folder_path):
        # Filtrage intelligent des dossiers
        dirs[:] = [d for d in dirs if d not in EXCLUDE_PATTERNS]
        for f in files:
            if f not in EXCLUDE_PATTERNS:
                fp = os.path.join(root, f)
                total_size += os.path.getsize(fp)
                file_count += 1
    return total_size, file_count


def estimate_ultra_time(size_bytes):
    # Basé sur une moyenne conservatrice de 5 Mo/s pour LZMA (dépend du CPU)
    seconds = size_bytes / (5 * 1024 * 1024)
    if seconds < 60:
        return f"env. {int(seconds)} secondes"
    else:
        return f"env. {int(seconds/60)} minute(s)"


def compress_folder():
    print(
        r"""
 ____            _    _             _     _           
/ ___| _   _  __| |  / \   _ __ ___| |__ (_)_   _____ 
\___ \| | | |/ _` | / _ \ | '__/ __| '_ \| \ \ / / _ \
 ___) | |_| | (_| |/ ___ \| | | (__| | | | |\ V /  __/
|____/ \__,_|\__,_/_/   \_\_|  \___|_| |_|_| \_/ \___|
    """
    )

    target_folder = (
        input("📂 Dossier à compresser (glissez-déposer ou nom) : ")
        .strip()
        .replace('"', "")
        .replace("'", "")
    )

    if not os.path.isdir(target_folder):
        print(f"[Erreur] '{target_folder}' n'est pas un dossier valide.")
        return

    folder_name = os.path.basename(os.path.normpath(target_folder))
    total_size, file_count = get_folder_size(target_folder)

    print(f"\n[Analyse] Dossier : {folder_name}")
    print(
        f"[Analyse] Taille à traiter : {format_size(total_size)} ({file_count} fichiers)"
    )
    print(
        f"[Note] Les dossiers inutiles ({', '.join(list(EXCLUDE_PATTERNS)[:3])}...) seront ignorés."
    )

    print("\n" + "=" * 50)
    print("🚀 MODES DE COMPRESSION")
    print("=" * 50)
    print("1. CLASSIQUE (Rapide, ZIP Deflate)")
    print("2. MEDIUM    (Équilibré, ZIP Bzip2)")
    print("3. ULTRA     (Maximum, Format .tar.xz / LZMA)")

    mode = input("\nVotre choix (1, 2 ou 3) : ").strip()

    # Paramètres selon le mode
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if mode == "1":
        ext = ".zip"
        comp_type = zipfile.ZIP_DEFLATED
        level = 6  # Niveau standard
        mode_label = "Classique"
    elif mode == "2":
        ext = ".zip"
        comp_type = zipfile.ZIP_BZIP2
        level = 9  # Maximum pour Bzip2
        mode_label = "Medium"
    elif mode == "3":
        ext = ".tar.xz"
        mode_label = "Ultra"
        print(
            f"\n⚠️  [Mode ULTRA] L'estimation de temps est de {estimate_ultra_time(total_size)}."
        )
        confirm = input("Voulez-vous continuer ? (o/n) : ").strip().lower()
        if confirm != "o":
            print("Opération annulée.")
            return
    else:
        print("[Erreur] Choix invalide.")
        return

    output_filename = f"{folder_name}_Archive_{timestamp}{ext}"
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(target_folder)), output_filename
    )

    start_time = time.time()
    print(f"\n[Compression] Mode {mode_label} en cours vers {output_filename}...")

    try:
        processed_files = 0

        if ext == ".zip":
            with zipfile.ZipFile(
                output_path, "w", compression=comp_type, compresslevel=level
            ) as zipf:
                for root, dirs, files in os.walk(target_folder):
                    dirs[:] = [d for d in dirs if d not in EXCLUDE_PATTERNS]
                    for file in files:
                        if file in EXCLUDE_PATTERNS:
                            continue
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, target_folder)
                        zipf.write(file_path, arcname)
                        processed_files += 1
                        if processed_files % 10 == 0 or processed_files == file_count:
                            percent = (processed_files / file_count) * 100
                            bar_length = 30
                            filled = int(bar_length * processed_files // file_count)
                            bar = "█" * filled + "░" * (bar_length - filled)
                            print(f"\r[Compression] |{bar}| {percent:.1f}% ({processed_files}/{file_count})", end="")

            # Vérification d'intégrité ZIP
            print("\n[Vérification] Analyse de l'intégrité du ZIP...")
            with zipfile.ZipFile(output_path, "r") as zipf:
                bad_file = zipf.testzip()
                if bad_file:
                    print(
                        f"❌ [Erreur] Archive corrompue détectée au fichier : {bad_file}"
                    )
                else:
                    print("✅ [Vérification] Archive ZIP valide.")

        else:  # Ultra mode (.tar.xz)
            with tarfile.open(output_path, "w:xz") as tar:
                # Note: tar.add n'a pas de compteur facile, on liste manuellement
                for root, dirs, files in os.walk(target_folder):
                    dirs[:] = [d for d in dirs if d not in EXCLUDE_PATTERNS]
                    for file in files:
                        if file in EXCLUDE_PATTERNS:
                            continue
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, target_folder)
                        tar.add(file_path, arcname=arcname)
                        processed_files += 1
                        if processed_files % 5 == 0 or processed_files == file_count:
                            percent = (processed_files / file_count) * 100
                            bar_length = 30
                            filled = int(bar_length * processed_files // file_count)
                            bar = "█" * filled + "░" * (bar_length - filled)
                            print(f"\r[Compression] |{bar}| {percent:.1f}% ({processed_files}/{file_count})", end="")
            print(f"\n✅ [Vérification] Archive TAR.XZ créée.")

        end_time = time.time()
        final_size = os.path.getsize(output_path)
        reduction = (1 - (final_size / total_size)) * 100 if total_size > 0 else 0

        print("\n" + "=" * 50)
        print("🎉 COMPRESSION TERMINÉE")
        print("=" * 50)
        print(f"⏱️  Temps écoulé     : {end_time - start_time:.2f} secondes")
        print(f"📦 Taille finale    : {format_size(final_size)}")
        print(f"📉 Gain d'espace    : {reduction:.2f}%")
        print(f"📁 Emplacement      : {output_path}")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ [Erreur Fatale] : {e}")
        if os.path.exists(output_path):
            os.remove(output_path)


if __name__ == "__main__":
    try:
        compress_folder()
    except KeyboardInterrupt:
        print("\n\n[Interruption] Opération annulée par l'utilisateur.")
        sys.exit(0)
