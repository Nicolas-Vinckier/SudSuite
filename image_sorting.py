import os
import shutil
import datetime
import re
import json
import random

CONFIG_FILE = "image_sorting_config.json"

mois_fr = {
    1: "Janvier",
    2: "Février",
    3: "Mars",
    4: "Avril",
    5: "Mai",
    6: "Juin",
    7: "Juillet",
    8: "Août",
    9: "Septembre",
    10: "Octobre",
    11: "Novembre",
    12: "Décembre",
    "01": "Janvier",
    "02": "Février",
    "03": "Mars",
    "04": "Avril",
    "05": "Mai",
    "06": "Juin",
    "07": "Juillet",
    "08": "Août",
    "09": "Septembre",
    "10": "Octobre",
    "11": "Novembre",
    "12": "Décembre",
    "January": "Janvier",
    "February": "Février",
    "March": "Mars",
    "April": "Avril",
    "May": "Mai",
    "June": "Juin",
    "July": "Juillet",
    "August": "Août",
    "September": "Septembre",
    "October": "Octobre",
    "November": "Novembre",
    "December": "Décembre",
}


def charger_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(
                "Fichier de configuration corrompu. Création d'une nouvelle configuration."
            )
            return None
    return None


def sauvegarder_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)


def detecter_format_nom(source):
    """Analyse un échantillon de fichiers pour deviner le format de date."""
    all_files = []
    if not os.path.exists(source):
        return None

    for root, dirs, files in os.walk(source):
        for f in files:
            if f.lower().endswith(
                (
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".bmp",
                    ".mp4",
                    ".avi",
                    ".mov",
                    ".mkv",
                )
            ):
                all_files.append(f)

    if not all_files:
        return None  # Aucun fichier à analyser

    # Échantillon de 10% (minimum 1, maximum len)
    sample_size = max(1, int(len(all_files) * 0.1))
    sample = random.sample(all_files, sample_size)

    scores = {"AAAAMMDD": 0, "DDMMAAAA": 0, "MMDDAAAA": 0}

    for filename in sample:
        # Test AAAAMMDD (4-2-2)
        m422 = re.search(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)", filename)
        if m422:
            y, m, d = m422.groups()
            if 1900 <= int(y) <= 2100 and 1 <= int(m) <= 12 and 1 <= int(d) <= 31:
                scores["AAAAMMDD"] += 1

        # Test 2-2-4 (DDMMAAAA ou MMDDAAAA)
        m224 = re.search(r"(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)", filename)
        if m224:
            g1, g2, y = m224.groups()
            if 1900 <= int(y) <= 2100:
                # DDMMAAAA
                if 1 <= int(g1) <= 31 and 1 <= int(g2) <= 12:
                    scores["DDMMAAAA"] += 1
                # MMDDAAAA
                if 1 <= int(g1) <= 12 and 1 <= int(g2) <= 31:
                    scores["MMDDAAAA"] += 1

    # On retourne le format avec le score le plus élevé (ou None si aucune détection n'est fiable)
    best_format = max(scores, key=scores.get)
    if scores[best_format] == 0:
        return None
    return best_format


def a_des_fichiers_media(source):
    """Vérifie si le dossier contient au moins un fichier média."""
    if not os.path.exists(source):
        return False
    for root, dirs, files in os.walk(source):
        for f in files:
            if f.lower().endswith(
                (
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".bmp",
                    ".mp4",
                    ".avi",
                    ".mov",
                    ".mkv",
                )
            ):
                return True
    return False


def demander_format_nom(source):
    """Gère la détection et la sélection manuelle du format de nom."""
    detecte = detecter_format_nom(source)
    format_nom = None

    if detecte:
        print(f"\n[Analyse] Analyse d'un echantillon de fichiers dans '{source}'...")
        print(f"Format de nom de fichier detecte : {detecte}")
        confirmation = input("Est-ce correct ? (o/n) : ").strip().lower()
        if confirmation == "o":
            format_nom = detecte
    else:
        print(
            f"\n[Info] Impossible de detecter automatiquement le format (noms de fichiers inconnus)."
        )

    if format_nom is None:
        print(
            "\nVeuillez choisir le format de date utilise dans vos noms de fichiers :"
        )
        print("1) AAAAMMDD (ex: 20231231)")
        print("2) DDMMAAAA (ex: 31122023)")
        print("3) MMDDAAAA (ex: 12312023)")
        choix_fmt = ""
        while choix_fmt not in ["1", "2", "3"]:
            choix_fmt = input("Votre choix (1, 2 ou 3) : ").strip()
        format_nom = {"1": "AAAAMMDD", "2": "DDMMAAAA", "3": "MMDDAAAA"}[choix_fmt]

    return format_nom


def configurer():
    print("\n--- Configuration du tri des médias ---")
    source = input("Dossier source (laisser vide pour 'Source_photo') : ").strip()
    if not source:
        source = "Source_photo"

    destination = input(
        "Dossier de destination (laisser vide pour 'Destination_photo') : "
    ).strip()
    if not destination:
        destination = "Destination_photo"

    print("\nComment souhaitez-vous extraire la date des fichiers ?")
    print(
        "1) Par la date de modification du fichier (recommandé pour les transferts simples)"
    )
    print("2) Par la date de création du fichier")
    print(
        "3) Par le nom du fichier (Idéal pour photos de téléphone, ex: IMG_20230101_120000.jpg)"
    )

    choix_tri = ""
    while choix_tri not in ["1", "2", "3"]:
        choix_tri = input("Votre choix (1, 2 ou 3) : ").strip()

    mode_tri = {"1": "modification", "2": "creation", "3": "nom"}[choix_tri]
    format_nom = None

    if mode_tri == "nom":
        # On ne pose la question QUE s'il y a déjà des fichiers
        if a_des_fichiers_media(source):
            format_nom = demander_format_nom(source)
        else:
            print(
                f"\n[Info] Dossier '{source}' vide. Le format sera demande lors du premier tri."
            )

    config = {
        "source": source,
        "destination": destination,
        "mode_tri": mode_tri,
        "format_nom": format_nom,
    }

    sauvegarder_config(config)
    print(f"Configuration sauvegardée dans {CONFIG_FILE}\n")
    return config


def get_date_from_file(filepath, filename, mode, format_nom=None):
    if mode == "nom":
        # Formats avec 4 chiffres en premier (AAAAMMDD)
        if format_nom == "AAAAMMDD" or format_nom is None:
            match = re.search(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)", filename)
            if match:
                annee, mois, jour = match.groups()
                if (
                    1900 <= int(annee) <= 2100
                    and 1 <= int(mois) <= 12
                    and 1 <= int(jour) <= 31
                ):
                    return annee, mois_fr.get(mois, mois)

        # Formats avec l'année à la fin (DDMMAAAA ou MMDDAAAA)
        elif format_nom in ["DDMMAAAA", "MMDDAAAA"]:
            match = re.search(r"(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)", filename)
            if match:
                g1, g2, annee = match.groups()
                if 1900 <= int(annee) <= 2100:
                    if format_nom == "DDMMAAAA":
                        # g1=jour, g2=mois
                        if 1 <= int(g1) <= 31 and 1 <= int(g2) <= 12:
                            return annee, mois_fr.get(g2, g2)
                    else:  # MMDDAAAA
                        # g1=mois, g2=jour
                        if 1 <= int(g1) <= 12 and 1 <= int(g2) <= 31:
                            return annee, mois_fr.get(g1, g1)

        # Alternative stricte (toujours basée sur AAAAMMDD pour les préfixes standards)
        match_strict = re.search(r"(IMG|VID|AMBI|PANO)_(\d{4})(\d{2})(\d{2})", filename)
        if match_strict:
            prefix, annee, mois, jour = match_strict.groups()
            return annee, mois_fr.get(mois, mois)

        print(
            f"[{filename}] Impossible d'extraire la date avec le format {format_nom}. Fichier non classé."
        )
        return None, None

    elif mode == "modification":
        dt = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
        mois_str = dt.strftime("%B").capitalize()
        return str(dt.year), mois_fr.get(mois_str, mois_str)

    elif mode == "creation":
        dt = datetime.datetime.fromtimestamp(os.path.getctime(filepath))
        mois_str = dt.strftime("%B").capitalize()
        return str(dt.year), mois_fr.get(mois_str, mois_str)

    return None, None


def copier_coller_media(config):
    source = config["source"]
    destination = config["destination"]
    mode_tri = config["mode_tri"]

    if not os.path.exists(source):
        os.makedirs(source)
        print("Répertoire source créé :", source)

    if not os.path.exists(destination):
        os.makedirs(destination)
        print("Répertoire de destination créé :", destination)

    destination_doublon = os.path.join(destination, "doublon")
    if not os.path.exists(destination_doublon):
        os.makedirs(destination_doublon)
        print("Répertoire des doublons créé :", destination_doublon)

    fichiers_traites = 0

    for root, dirs, files in os.walk(source):
        for filename in files:
            filepath = os.path.join(root, filename)

            # Vérifier l'extension pour ignorer les fichiers qui ne sont pas des médias
            if not filename.lower().endswith(
                (
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".bmp",
                    ".mp4",
                    ".avi",
                    ".mov",
                    ".mkv",
                )
            ):
                continue

            annee, mois = get_date_from_file(
                filepath, filename, mode_tri, config.get("format_nom")
            )

            if not annee or not mois:
                continue

            destination_annee = os.path.join(destination, annee)
            destination_mois = os.path.join(destination_annee, mois)

            if not os.path.exists(destination_annee):
                os.makedirs(destination_annee)

            if not os.path.exists(destination_mois):
                os.makedirs(destination_mois)

            destination_filepath = os.path.join(destination_mois, filename)

            if os.path.exists(destination_filepath):
                destination_doublon_mois = os.path.join(destination_doublon, mois)
                if not os.path.exists(destination_doublon_mois):
                    os.makedirs(destination_doublon_mois)

                shutil.move(filepath, os.path.join(destination_doublon_mois, filename))
                print(
                    f"Doublon - Fichier deplace : {os.path.join(destination_doublon_mois, filename)}"
                )
            else:
                shutil.move(filepath, destination_filepath)
                print(f"Fichier deplace : {destination_filepath}")

            fichiers_traites += 1

    print(f"\nNettoyage de '{source}'...")
    # Supprimer les dossiers vides de la source
    for root, dirs, files in os.walk(source, topdown=False):
        for directory in dirs:
            dir_path = os.path.join(root, directory)
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    print(f"Dossier vide supprimé : {dir_path}")
            except OSError:
                pass

    print(f"\nTermine ! {fichiers_traites} fichiers medias traites.")


def tri_inverse(config):
    """Déplace tous les fichiers média de la destination vers la source."""
    source = config["source"]
    destination = config["destination"]

    if not os.path.exists(destination):
        print(f"[Erreur] Le dossier destination '{destination}' n'existe pas.")
        return

    if not os.path.exists(source):
        os.makedirs(source)

    fichiers_deplaces = 0
    extensions_media = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
    )

    print(f"\n--- Lancement du tri inverse (Dest -> Source) ---")

    for root, dirs, files in os.walk(destination):
        # Ignorer le dossier 'doublon' s'il existe et qu'on ne veut pas y toucher
        # (Ou on peut choisir de le vider aussi, ici on vide tout)
        for filename in files:
            if filename.lower().endswith(extensions_media):
                filepath = os.path.join(root, filename)
                dest_path = os.path.join(source, filename)

                # Gestion simple si le fichier existe déjà dans la source
                # (on ajoute un timestamp pour éviter l'écrasement)
                if os.path.exists(dest_path):
                    name, ext = os.path.splitext(filename)
                    dest_path = os.path.join(
                        source,
                        f"{name}_restaure_{datetime.datetime.now().strftime('%H%M%S')}{ext}",
                    )

                try:
                    shutil.move(filepath, dest_path)
                    print(f"Restaure : {filename} -> {source}")
                    fichiers_deplaces += 1
                except Exception as e:
                    print(f"[Erreur] Impossible de deplacer {filename} : {e}")

    print(f"\nNettoyage de '{destination}'...")
    # Supprimer les dossiers vides de la destination
    for root, dirs, files in os.walk(destination, topdown=False):
        for directory in dirs:
            dir_path = os.path.join(root, directory)
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    print(f"Dossier vide supprime : {dir_path}")
            except OSError:
                pass

    print(f"\nTermine ! {fichiers_deplaces} fichiers restaures vers '{source}'.")


def full_cleaning(config):
    """Supprime la configuration et TOUS les médias dans source et destination."""
    source = config.get("source")
    destination = config.get("destination")

    print("\n" + "!" * 50)
    print("ATTENTION : CETTE ACTION EST IRREVERSIBLE")
    print("!" * 50)

    # Comptage des fichiers et dossiers
    total_files = 0
    total_dirs = 0

    for path in [source, destination]:
        if os.path.exists(path):
            for root, dirs, files in os.walk(path):
                total_files += len(files)
                total_dirs += len(dirs)
            total_dirs += 1  # Le dossier racine lui-même

    print(f"\nCette operation va supprimer :")
    print(f"  - Le fichier de configuration : {CONFIG_FILE}")
    print(f"  - Dossier Source      : '{source}'")
    print(f"  - Dossier Destination : '{destination}'")
    print(f"\nBILAN DE SUPPRESSION :")
    print(f"  - Env. {total_files} fichiers seront SUPPRIMES DEFINITIVEMENT.")
    print(f"  - Env. {total_dirs} dossiers seront SUPPRIMES DEFINITIVEMENT.")

    confirmation = input(
        "\nEtes-vous ABSOLUMENT sûr de vouloir tout supprimer ? (ecrire 'OUI' en majuscules) : "
    ).strip()

    if confirmation == "OUI":
        # Suppression des dossiers
        for path in [source, destination]:
            if os.path.exists(path):
                try:
                    shutil.rmtree(path)
                    print(f"Suppression de : {path} [OK]")
                except Exception as e:
                    print(f"[Erreur] Impossible de supprimer {path} : {e}")

        # Suppression du fichier de config
        if os.path.exists(CONFIG_FILE):
            try:
                os.remove(CONFIG_FILE)
                print(f"Suppression de : {CONFIG_FILE} [OK]")
            except Exception as e:
                print(f"[Erreur] Impossible de supprimer {CONFIG_FILE} : {e}")

        print("\n[Nettoyage termine] Tout a ete reinitialise.")
    else:
        print("\nOperation annulee. Rien n'a ete supprime.")


def main():
    print(
        r"""
 ____            _ ____             _   _             
/ ___| _   _  __| / ___|  ___  _ __| |_(_)_ __   __ _ 
\___ \| | | |/ _` \___ \ / _ \| '__| __| | '_ \ / _` |
 ___) | |_| | (_| |___) | (_) | |  | |_| | | | | (_| |
|____/ \__,_|\__,_|____/ \___/|_|   \__|_|_| |_|\__, |
                                                |___/ 
    """
    )

    config = charger_config()

    if config:
        print("\nUne configuration existante a été trouvée :")
        print(f"  - Dossier source      : {config.get('source')}")
        print(f"  - Dossier destination : {config.get('destination')}")
        print(f"  - Mode de tri         : {config.get('mode_tri')}")
        if config.get("mode_tri") == "nom":
            print(f"  - Format de nom       : {config.get('format_nom')}")
        print("\nQue voulez-vous faire ?")
        print("1) Utiliser la configuration présente")
        print("2) Recommencer la configuration / From scratch")
        print("3) Trie inverse (Deplacer Destination -> Source)")
        print("4) Full cleaning (TOUT SUPPRIMER : Photos + Config)")

        choix = ""
        while choix not in ["1", "2", "3", "4"]:
            choix = input("Votre choix (1, 2, 3 ou 4) : ").strip()

        if choix == "2":
            config = configurer()
        elif choix == "3":
            tri_inverse(config)
            return
        elif choix == "4":
            full_cleaning(config)
            return
    else:
        print("\nAucune configuration trouvée. Création d'une nouvelle configuration.")
        config = configurer()

    # Si on est en mode nom et que le format n'est pas encore défini (ex: dossier était vide au départ)
    if config.get("mode_tri") == "nom" and config.get("format_nom") is None:
        if a_des_fichiers_media(config["source"]):
            config["format_nom"] = demander_format_nom(config["source"])
            # On met à jour le fichier de config avec le format maintenant connu
            sauvegarder_config(config)

    print("\n--- Lancement du tri ---")
    copier_coller_media(config)


if __name__ == "__main__":
    main()
