import os
import zipfile
import tarfile
import time
import datetime
import sys
import argparse
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
    # Basé sur une moyenne conservatrice de 5 Mo/s pour LZMA
    seconds = size_bytes / (5 * 1024 * 1024)

    if seconds < 60:
        return f"env. {int(seconds)} secondes"
    else:
        return f"env. {int(seconds / 60)} minute(s)"


def clean_input_path(value):
    return value.strip().replace('"', "").replace("'", "")


def resolve_archive_output_path(output_input, default_output_dir, default_filename, expected_ext):
    """
    Résout le chemin final de l'archive.

    - Si output_input est vide :
      -> archive à côté du dossier source.

    - Si output_input désigne un dossier :
      -> archive dans ce dossier avec le nom généré automatiquement.

    - Si output_input désigne un fichier avec extension :
      -> archive à ce chemin exact, avec extension corrigée si nécessaire.

    - Si output_input est relatif :
      -> chemin résolu depuis le répertoire courant.
    """

    default_output_dir = Path(default_output_dir).resolve()

    if not output_input:
        return default_output_dir / default_filename

    candidate = Path(output_input).expanduser()

    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()

    # Cas 1 : chemin existant et dossier
    if candidate.exists() and candidate.is_dir():
        output_dir = candidate
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / default_filename

    # Cas 2 : chemin avec extension => considéré comme un fichier de sortie
    if candidate.suffix:
        output_file = candidate

        # Correction automatique de l'extension si elle ne correspond pas au mode choisi
        if not output_file.name.lower().endswith(expected_ext.lower()):
            output_file = output_file.with_suffix(expected_ext)

        output_file.parent.mkdir(parents=True, exist_ok=True)
        return output_file

    # Cas 3 : chemin sans extension => considéré comme un dossier de sortie
    output_dir = candidate
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / default_filename


def print_progress(processed_files, file_count):
    if file_count == 0:
        return

    percent = (processed_files / file_count) * 100
    bar_length = 30
    filled = int(bar_length * processed_files // file_count)
    bar = "█" * filled + "░" * (bar_length - filled)

    print(
        f"\r[Compression] |{bar}| {percent:.1f}% ({processed_files}/{file_count})",
        end=""
    )


def compress_folder(cli_args=None):
    print(
        r"""
 ____            _    _             _     _           
/ ___| _   _  __| |  / \   _ __ ___| |__ (_)_   _____ 
\___ \| | | |/ _` | / _ \ | '__/ __| '_ \| \ \ / / _ \
 ___) | |_| | (_| |/ ___ \| | | (__| | | | |\ V /  __/
|____/ \__,_|\__,_/_/   \_\_|  \___|_| |_|_| \_/ \___|
    """
    )

    if cli_args and cli_args.input:
        target_folder = clean_input_path(cli_args.input)
    else:
        target_folder = clean_input_path(
            input("📂 Dossier à compresser (glissez-déposer ou nom) : ")
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

    if cli_args and cli_args.mode:
        mode = cli_args.mode
    else:
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
        level = 6
        mode_label = "Classique"

    elif mode == "2":
        ext = ".zip"
        comp_type = zipfile.ZIP_BZIP2
        level = 9
        mode_label = "Medium"

    elif mode == "3":
        ext = ".tar.xz"
        mode_label = "Ultra"

        print(
            f"\n⚠️  [Mode ULTRA] L'estimation de temps est de {estimate_ultra_time(total_size)}."
        )
        if cli_args and cli_args.mode:
            pass
        else:
            confirm = input("Voulez-vous continuer ? (o/n) : ").strip().lower()

            if confirm != "o":
                print("Opération annulée.")
                return

    else:
        print("[Erreur] Choix invalide.")
        return

    output_filename = f"{folder_name}_Archive_{timestamp}{ext}"

    if cli_args and cli_args.output is not None:
        output_input = clean_input_path(cli_args.output)
    else:
        print("\n" + "=" * 50)
        print("📁 SORTIE DE L'ARCHIVE")
        print("=" * 50)

        output_input = clean_input_path(
            input(
                "Chemin de sortie, absolu ou relatif "
                "(Entrée = archive à côté du dossier source) : "
            )
        )

    default_output_dir = Path(target_folder).resolve().parent

    try:
        output_path = resolve_archive_output_path(
            output_input=output_input,
            default_output_dir=default_output_dir,
            default_filename=output_filename,
            expected_ext=ext,
        )
    except Exception as e:
        print(f"[Erreur] Impossible de préparer le chemin de sortie : {e}")
        return

    start_time = time.time()
    print(f"\n[Compression] Mode {mode_label} en cours vers :")
    print(f"{output_path}")

    try:
        processed_files = 0

        if ext == ".zip":
            with zipfile.ZipFile(
                output_path,
                "w",
                compression=comp_type,
                compresslevel=level,
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
                            print_progress(processed_files, file_count)

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

        else:
            # Mode Ultra (.tar.xz)
            with tarfile.open(output_path, "w:xz") as tar:
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
                            print_progress(processed_files, file_count)

            print("\n✅ [Vérification] Archive TAR.XZ créée.")

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

        if "output_path" in locals() and os.path.exists(output_path):
            os.remove(output_path)


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="SudMedia Folder Compressor")
        parser.add_argument("-input", "--input", "-i", help="Dossier à compresser")
        parser.add_argument("-mode", "--mode", "-m", choices=["1", "2", "3"], help="Mode de compression (1, 2 ou 3)")
        parser.add_argument("-output", "--output", "-o", help="Chemin de sortie de l'archive")
        
        args = parser.parse_args()
        compress_folder(args)
    except KeyboardInterrupt:
        print("\n\n[Interruption] Opération annulée par l'utilisateur.")
        sys.exit(0)