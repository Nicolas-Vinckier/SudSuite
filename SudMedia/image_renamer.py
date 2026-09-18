import os
import datetime
import sys
import shutil

try:
    from .sudmedia_utils import (
        IMAGE_EXTENSIONS,
        MEDIA_EXTENSIONS,
        Progress,
        VIDEO_EXTENSIONS,
        clean_input_path,
        configure_console_output,
    )
except ImportError:
    from sudmedia_utils import (
        IMAGE_EXTENSIONS,
        MEDIA_EXTENSIONS,
        Progress,
        VIDEO_EXTENSIONS,
        clean_input_path,
        configure_console_output,
    )

configure_console_output()

# --- ASCII Header ---
HEADER = r"""
  ____            _ ____                                            
 / ___| _   _  __| |  _ \ ___ _ __   __ _ _ __ ___   ___ _ __ 
 \___ \| | | |/ _` | |_) / _ \ '_ \ / _` | '_ ` _ \ / _ \ '__|
  ___) | |_| | (_| |  _ <  __/ | | | (_| | | | | | |  __/ |   
 |____/ \__,_|\__,_|_| \_\___|_| |_|\__,_|_| |_| |_|\___|_|   

"""

# Alias conservés pour les éventuels imports externes de l'ancien script.
EXTENSIONS_IMAGE = IMAGE_EXTENSIONS
EXTENSIONS_VIDEO = VIDEO_EXTENSIONS
EXTENSIONS_MEDIA = MEDIA_EXTENSIONS


def format_timestamp(ts, pattern):
    """
    Formate un timestamp selon un motif personnalisé.
    Tokens supportés : YYYY, MM, DD, HH, mm, SS
    """
    dt = datetime.datetime.fromtimestamp(ts)

    # Remplacements
    result = pattern.replace("YYYY", dt.strftime("%Y"))
    result = result.replace("MM", dt.strftime("%m"))
    result = result.replace("DD", dt.strftime("%d"))
    result = result.replace("HH", dt.strftime("%H"))
    result = result.replace("mm", dt.strftime("%M"))
    result = result.replace("SS", dt.strftime("%S"))

    return result


def get_unique_filename(directory, base_name, extension):
    """
    Gère les collisions en utilisant le token '#' du motif ou en ajoutant un index.
    """
    full_path = os.path.join(directory, f"{base_name}{extension}")

    # Si le fichier n'existe pas, on le retourne tel quel (sans s'occuper du # si non présent)
    if not os.path.exists(full_path):
        # Si le pattern contenait un # mais qu'on n'a pas de collision, on le remplace par '1' ou on l'enlève?
        # Le plus propre est de remplacer le '#' par '1' par défaut si présent.
        clean_name = base_name.replace("#", "1")
        final_path = os.path.join(directory, f"{clean_name}{extension}")
        if not os.path.exists(final_path):
            return clean_name

    # S'il y a collision ou si on doit itérer
    counter = 1
    while True:
        if "#" in base_name:
            new_name = base_name.replace("#", str(counter))
        else:
            new_name = f"{base_name}_{counter}"

        new_path = os.path.join(directory, f"{new_name}{extension}")
        if not os.path.exists(new_path):
            return new_name
        counter += 1


def run_rename():
    print(HEADER)

    # 1. Sélection du dossier
    while True:
        folder_path = (
            clean_input_path(
                input("\n📂 Chemin du dossier à traiter (ou glissez-déposez) : ")
            )
        )
        if os.path.isdir(folder_path):
            break
        print("❌ Dossier invalide. Veuillez réessayer.")

    # 2. Lister les fichiers
    files = [f for f in os.listdir(folder_path) if f.lower().endswith(EXTENSIONS_MEDIA)]

    if not files:
        print("⚠️ Aucun fichier média trouvé dans ce dossier.")
        return

    print(f"✅ {len(files)} fichiers trouvés.")

    # 3. Demander le format
    print("\n--- Format de renommage ---")
    print(
        "Tokens : YYYY (Année), MM (Mois), DD (Jour), HH (Heure), mm (Minute), SS (Seconde)"
    )
    print(
        "Utilisez '#' pour l'index d'itération (obligatoire si plusieurs images par seconde)."
    )
    print("Exemple : YYYYMMDD_HHmmSS_#")

    default_format = "YYYYMMDD_HHmmSS_#"
    rename_format = input(f"Format souhaité (défaut: {default_format}) : ").strip()
    if not rename_format:
        rename_format = default_format

    # 4. Simulation / Prévisualisation
    print("\n🧐 Prévisualisation (5 premiers fichiers) :")
    preview_limit = 5
    for i, filename in enumerate(files[:preview_limit]):
        filepath = os.path.join(folder_path, filename)
        mtime = os.path.getmtime(filepath)

        name_only, extension = os.path.splitext(filename)
        base_renamed = format_timestamp(mtime, rename_format)

        # Note: La prévisualisation ne simule pas parfaitement les collisions inter-fichiers
        # car elle est individuelle, mais ça donne une idée.
        print(f"  {filename}  ->  {base_renamed}{extension}")

    # 5. Confirmation
    dest_folder = folder_path.rstrip("/\\") + "_renamed"
    print(f"\n📂 Dossier de destination : {dest_folder}")

    confirm = (
        input("\n🚀 Confirmer la copie et le renommage ? (O/N) : ").strip().upper()
    )
    if confirm != "O":
        print("❌ Opération annulée.")
        return

    # Création du dossier de destination
    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)
        print(f"✅ Dossier '{os.path.basename(dest_folder)}' créé.")

    # 6. Exécution
    print("\n🔄 Traitement en cours...")
    renamed_count = 0
    error_count = 0
    file_count = len(files)
    progress = Progress(file_count, label="Renommage").start()

    # On trie les fichiers par date de modification pour garder une logique d'indexation
    files.sort(key=lambda x: os.path.getmtime(os.path.join(folder_path, x)))

    try:
        for filename in files:
            old_path = os.path.join(folder_path, filename)
            mtime = os.path.getmtime(old_path)
            _name_only, extension = os.path.splitext(filename)
            base_new_name = format_timestamp(mtime, rename_format)
            final_name = get_unique_filename(dest_folder, base_new_name, extension)
            new_path = os.path.join(dest_folder, f"{final_name}{extension}")

            try:
                shutil.copy2(old_path, new_path)
                renamed_count += 1
                status = "Copié"
            except OSError:
                error_count += 1
                status = "Erreur"
            progress.complete_file(item=filename, status=status)
        progress.finish()
    except BaseException:
        progress.abort()
        raise

    # 7. Rapport final
    print("\n✅ Opération terminée !")
    print(f"📊 Fichiers copiés et renommés : {renamed_count}")
    print(f"📂 Retrouvez vos fichiers dans : {dest_folder}")
    if error_count > 0:
        print(f"⚠️ Erreurs rencontrées : {error_count}")


def main():
    try:
        run_rename()
    except KeyboardInterrupt:
        print("\n\n👋 Sortie du programme.")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Une erreur inattendue est survenue : {e}")
        input("\nAppuyez sur Entrée pour quitter...")


if __name__ == "__main__":
    main()
