import os
import sys
import time
import json
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SudCore.files import atomic_write_json


def print_header():
    print(
        r"""
 ____            ___     __          _ _   ____                   
/ ___| _   _  __| \ \   / /_ _ _   _| | |_/ ___| _   _ _ __   ___ 
\___ \| | | |/ _` |\ \ / / _` | | | | | __\___ \| | | | '_ \ / __|
 ___) | |_| | (_| | \ V / (_| | |_| | | |_ ___) | |_| | | | | (__ 
|____/ \__,_|\__,_|  \_/ \__,_|\__,_|_|\__|____/ \__, |_| |_|\___|
                                                 |___/            
    """
    )


try:
    from SudSecurity.vault import VaultError, create_key, decrypt_file, default_key_path, encrypt_file, load_key
except ImportError:
    try:
        print_header()
    except UnicodeEncodeError:
        # Fallback if the terminal doesn't support emojis
        print("\n === [SECURE] Sud Vault Sync === \n")
    print("❌ La bibliothèque 'cryptography' est manquante.")
    print("⚠️ Veuillez l'essayer d'installer avec : py -m pip install cryptography")
    sys.exit(1)

# Configuration
STATE_FILE = ".sudvault_state.json"
EXTENSION = ".sud"
IGNORED_DIRS = {".git", "node_modules", "__pycache__"}

# Emojis supportés ou fallback text
UTF_8 = (getattr(sys.stdout, "encoding", "") or "").lower() == "utf-8"
E = {
    "LOCK": "🔒" if UTF_8 else "[LOCK]",
    "UNLOCK": "🔓" if UTF_8 else "[UNLOCK]",
    "CLOUD": "☁️" if UTF_8 else "[CLOUD]",
    "FOLDER": "📁" if UTF_8 else "[FOLDER]",
    "SYNC": "🔄" if UTF_8 else "[SYNC]",
    "SUCCESS": "✅" if UTF_8 else "[OK]",
    "ERROR": "❌" if UTF_8 else "[ERROR]",
    "WARN": "⚠️" if UTF_8 else "[WARN]",
    "ROCKET": "🚀" if UTF_8 else "[START]",
    "FILE": "📄" if UTF_8 else "[FILE]",
    "BOX": "📦" if UTF_8 else "[SIZE]",
    "TRASH": "🗑️" if UTF_8 else "[DEL]",
    "SHIELD": "🛡️" if UTF_8 else "[SHIELD]",
    "STOP": "⏹️" if UTF_8 else "[STOP]",
    "BYE": "👋" if UTF_8 else "[BYE]",
    "ALERT": "🚨" if UTF_8 else "[ALERT]",
    "POINTER": "👉" if UTF_8 else ">",
}


def safe_print(msg, end="\n"):
    """Imprime un message en gérant les erreurs d'encodage sur Windows."""
    try:
        print(msg, end=end)
    except UnicodeEncodeError:
        # Si ça crash, on nettoie les caractères non-ASCII
        clean_msg = msg.encode("ascii", "ignore").decode("ascii")
        print(clean_msg, end=end)


def format_size(size_bytes):
    """Formate une taille en octets vers une unité lisible."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def manage_key():
    """Charge la clé de chiffrement ou propose d'en générer une."""
    key_path = default_key_path()
    fernet = load_key(key_path)
    if fernet is not None:
        safe_print(f"{E['SUCCESS']} Clé de chiffrement chargée ({key_path}).")
        return fernet

    safe_print(f"{E['WARN']} Clé de chiffrement introuvable : {key_path}")
    rep = input("Voulez-vous générer une nouvelle clé ? (O/N) : ").strip().upper()
    if rep != "O":
        safe_print(f"{E['ERROR']} Opération annulée, aucune clé disponible.")
        sys.exit(1)

    fernet = create_key(key_path)
    safe_print(f"{E['SUCCESS']} Nouvelle clé générée et sauvegardée : {key_path}")
    safe_print(
        f"{E['ALERT']} ATTENTION : copiez MANUELLEMENT ce fichier sur l'autre PC"
    )
    safe_print("   pour pouvoir déchiffrer vos fichiers. Ne le perdez pas, ne le partagez pas !")
    return fernet


def is_temporary(filename):
    """Fichiers temporaires des écritures atomiques, à ne jamais synchroniser."""
    return filename.startswith(".") and filename.endswith(".tmp")


def mode_encryption(fernet):
    safe_print(f"\n--- {E['LOCK']} Mode Chiffrement (Local -> Cloud) ---")
    local_dir = input(
        f"{E['FOLDER']} Entrez le chemin du dossier local (fichiers clairs) : "
    ).strip()
    cloud_dir = input(
        f"{E['CLOUD']} Entrez le chemin du dossier distant (Cloud) : "
    ).strip()

    if not os.path.isdir(local_dir):
        safe_print(f"{E['ERROR']} Dossier local introuvable.")
        return

    os.makedirs(cloud_dir, exist_ok=True)

    start_time = time.time()
    files_processed = 0
    total_size = 0

    safe_print(f"\n{E['ROCKET']} Début du chiffrement...")

    for root, dirs, files in os.walk(local_dir):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for file in files:
            if file == STATE_FILE or is_temporary(file):
                continue
            src_path = os.path.join(root, file)
            rel_path = os.path.relpath(src_path, local_dir)
            dst_path = os.path.join(cloud_dir, rel_path + EXTENSION)

            safe_print(f"{E['LOCK']} Chiffrement : {rel_path} ...", end=" ")
            try:
                size = encrypt_file(fernet, src_path, dst_path)
                files_processed += 1
                total_size += size
                safe_print(E["SUCCESS"])
            except (OSError, VaultError) as e:
                safe_print(f"{E['ERROR']} Erreur: {e}")

    elapsed = time.time() - start_time
    safe_print(f"\n{E['SUCCESS']} Terminé en {elapsed:.2f}s !")
    safe_print(f"{E['FILE']} Fichiers traités : {files_processed}")
    safe_print(f"{E['BOX']} Taille totale traitée : {format_size(total_size)}\n")


def mode_decryption(fernet):
    safe_print(f"\n--- {E['UNLOCK']} Mode Déchiffrement (Cloud -> Local) ---")
    cloud_dir = input(
        f"{E['CLOUD']} Entrez le chemin du dossier distant (Cloud) : "
    ).strip()
    local_dir = input(
        f"{E['FOLDER']} Entrez le chemin du dossier local (où recréer les fichiers clairs) : "
    ).strip()

    if not os.path.isdir(cloud_dir):
        safe_print(f"{E['ERROR']} Dossier distant introuvable.")
        return

    os.makedirs(local_dir, exist_ok=True)

    start_time = time.time()
    files_processed = 0
    total_size = 0

    safe_print(f"\n{E['ROCKET']} Début du déchiffrement...")

    for root, dirs, files in os.walk(cloud_dir):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for file in files:
            if not file.endswith(EXTENSION) or is_temporary(file):
                continue

            src_path = os.path.join(root, file)
            rel_path_with_ext = os.path.relpath(src_path, cloud_dir)
            rel_path = rel_path_with_ext[: -len(EXTENSION)]
            dst_path = os.path.join(local_dir, rel_path)

            safe_print(
                f"{E['UNLOCK']} Déchiffrement : {rel_path_with_ext} ...", end=" "
            )
            try:
                size = decrypt_file(fernet, src_path, dst_path)
                files_processed += 1
                total_size += size
                safe_print(E["SUCCESS"])
            except (OSError, VaultError) as e:
                safe_print(f"{E['ERROR']} Erreur: {e}")

    elapsed = time.time() - start_time
    safe_print(f"\n{E['SUCCESS']} Terminé en {elapsed:.2f}s !")
    safe_print(f"{E['FILE']} Fichiers traités : {files_processed}")
    safe_print(f"{E['BOX']} Taille totale restaurée : {format_size(total_size)}\n")


def sync_step(fernet, local_dir, cloud_dir, state):
    """Passe de synchronisation bidirectionnelle intelligente."""
    changed = False

    local_files = {}
    if os.path.exists(local_dir):
        for root, dirs, files in os.walk(local_dir):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            for file in files:
                if file == STATE_FILE or is_temporary(file):
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, local_dir).replace("\\", "/")
                local_files[rel_path] = os.path.getmtime(full_path)

    cloud_files = {}
    if os.path.exists(cloud_dir):
        for root, dirs, files in os.walk(cloud_dir):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            for file in files:
                if not file.endswith(EXTENSION) or is_temporary(file):
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, cloud_dir)[
                    : -len(EXTENSION)
                ].replace("\\", "/")
                cloud_files[rel_path] = os.path.getmtime(full_path)

    all_known_paths = set(state.keys())
    current_paths = set(local_files.keys()).union(set(cloud_files.keys()))

    for rel_path in current_paths:
        local_mtime = local_files.get(rel_path)
        cloud_mtime = cloud_files.get(rel_path)

        known_local_mtime = state.get(rel_path, {}).get("local_mtime")
        known_cloud_mtime = state.get(rel_path, {}).get("cloud_mtime")

        local_target = os.path.join(local_dir, os.path.normpath(rel_path))
        cloud_target = os.path.join(cloud_dir, os.path.normpath(rel_path) + EXTENSION)

        try:
            # Existe seulement en local
            if local_mtime and not cloud_mtime:
                if rel_path in state and known_cloud_mtime is not None:
                    # Supprimé sur le cloud -> supprimer en local
                    safe_print(
                        f"{E['TRASH']} [Cloud -> Local] Suppression : {rel_path}"
                    )
                    os.remove(local_target)
                    state.pop(rel_path, None)
                    changed = True
                else:
                    # Nouveau fichier local -> chiffrer vers cloud
                    safe_print(
                        f"{E['LOCK']} [Local -> Cloud] Ajout chiffré : {rel_path}"
                    )
                    encrypt_file(fernet, local_target, cloud_target)
                    state[rel_path] = {
                        "local_mtime": os.path.getmtime(local_target),
                        "cloud_mtime": os.path.getmtime(cloud_target),
                    }
                    changed = True

            # Existe seulement dans le cloud
            elif cloud_mtime and not local_mtime:
                if rel_path in state and known_local_mtime is not None:
                    # Supprimé en local -> supprimer du cloud
                    safe_print(
                        f"{E['TRASH']} [Local -> Cloud] Suppression : {rel_path + EXTENSION}"
                    )
                    os.remove(cloud_target)
                    state.pop(rel_path, None)
                    changed = True
                else:
                    # Nouveau fichier cloud -> déchiffrer vers local
                    safe_print(
                        f"{E['UNLOCK']} [Cloud -> Local] Ajout déchiffré : {rel_path}"
                    )
                    decrypt_file(fernet, cloud_target, local_target)
                    state[rel_path] = {
                        "local_mtime": os.path.getmtime(local_target),
                        "cloud_mtime": os.path.getmtime(cloud_target),
                    }
                    changed = True

            # Existe aux deux endroits
            elif local_mtime and cloud_mtime:
                if known_local_mtime and local_mtime > known_local_mtime:
                    safe_print(
                        f"{E['SYNC']} [Local -> Cloud] Maj chiffrée : {rel_path}"
                    )
                    encrypt_file(fernet, local_target, cloud_target)
                    state[rel_path] = {
                        "local_mtime": os.path.getmtime(local_target),
                        "cloud_mtime": os.path.getmtime(cloud_target),
                    }
                    changed = True
                elif known_cloud_mtime and cloud_mtime > known_cloud_mtime:
                    safe_print(
                        f"{E['SYNC']} [Cloud -> Local] Maj déchiffrée : {rel_path}"
                    )
                    decrypt_file(fernet, cloud_target, local_target)
                    state[rel_path] = {
                        "local_mtime": os.path.getmtime(local_target),
                        "cloud_mtime": os.path.getmtime(cloud_target),
                    }
                    changed = True
                elif rel_path not in state:
                    state[rel_path] = {
                        "local_mtime": local_mtime,
                        "cloud_mtime": cloud_mtime,
                    }
                    changed = True
        except (OSError, VaultError) as e:
            safe_print(f"{E['WARN']} Erreur de synchronisation sur '{rel_path}': {e}")

    # Nettoyage des fichiers supprimés des deux côtés a priori
    for rel_path in all_known_paths:
        if rel_path not in current_paths:
            state.pop(rel_path, None)
            changed = True

    return changed


def get_state_path(local_dir):
    return os.path.join(local_dir, STATE_FILE)


def load_state(local_dir):
    path = get_state_path(local_dir)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}
    return {}


def save_state(local_dir, state):
    path = get_state_path(local_dir)
    atomic_write_json(path, state)


def mode_sync(fernet):
    safe_print(f"\n--- {E['SYNC']} Mode Synchronisation Continue ---")
    safe_print(
        f"{E['WARN']} ATTENTION : Ce mode REPRODUIT LES SUPPRESSIONS des deux côtés."
    )
    local_dir = input(f"{E['FOLDER']} Entrez le chemin du dossier local : ").strip()
    cloud_dir = input(
        f"{E['CLOUD']} Entrez le chemin du dossier distant (Cloud) : "
    ).strip()

    os.makedirs(local_dir, exist_ok=True)
    os.makedirs(cloud_dir, exist_ok=True)

    state = load_state(local_dir)

    safe_print(
        f"\n{E['SHIELD']} Démarrage de la surveillance... (Appuyez sur Ctrl+C pour arrêter)"
    )

    try:
        while True:
            changed = sync_step(fernet, local_dir, cloud_dir, state)
            if changed:
                save_state(local_dir, state)
            time.sleep(3)
    except KeyboardInterrupt:
        safe_print(
            f"\n\n{E['STOP']} Arrêt de la synchronisation continue demandé par l'utilisateur."
        )
        save_state(local_dir, state)
        safe_print(f"{E['SUCCESS']} État sauvegardé. À bientôt !")


def main():
    try:
        print_header()
    except UnicodeEncodeError:
        pass
    fernet = manage_key()

    while True:
        safe_print("\n" + "=" * 40)
        safe_print(" MENU PRINCIPAL - SUD VAULT SYNC")
        safe_print("=" * 40)
        safe_print(
            f"1. {E['LOCK']} Chiffrer un dossier complet (Local -> Cloud) [Copie]"
        )
        safe_print(
            f"2. {E['UNLOCK']} Déchiffrer un dossier complet (Cloud -> Local) [Copie]"
        )
        safe_print(
            f"3. {E['SYNC']} Lancer la Synchronisation Continue (Bidirectionnelle)"
        )
        safe_print(f"0. {E['ERROR']} Quitter")
        safe_print("=" * 40)

        choix = input(f"\n{E['POINTER']} Votre choix : ").strip()

        if choix == "1":
            mode_encryption(fernet)
        elif choix == "2":
            mode_decryption(fernet)
        elif choix == "3":
            mode_sync(fernet)
        elif choix == "0":
            safe_print(f"{E['BYE']} Au revoir !")
            break
        else:
            safe_print(f"{E['ERROR']} Option invalide.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        safe_print(f"\n\n{E['ERROR']} Programme interrompu (Ctrl+C). À bientôt !")
        sys.exit(0)
