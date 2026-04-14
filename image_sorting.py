import os
import shutil
import datetime
import re
import json

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

    config = {"source": source, "destination": destination, "mode_tri": mode_tri}

    sauvegarder_config(config)
    print(f"Configuration sauvegardée dans {CONFIG_FILE}\n")
    return config


def get_date_from_file(filepath, filename, mode):
    if mode == "nom":
        # Recherche un motif du type YYYYMMDD n'importe où dans le nom
        # On évite que ce soit précédé ou suivi par d'autres chiffres tout de suite
        match = re.search(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)", filename)
        if match:
            annee, mois, jour = match.groups()
            if (
                1900 <= int(annee) <= 2100
                and 1 <= int(mois) <= 12
                and 1 <= int(jour) <= 31
            ):
                return annee, mois_fr.get(mois, mois)

        # Alternative stricte: au cas où la regex ci-dessus a échoué
        match_strict = re.search(r"(IMG|VID|AMBI|PANO)_(\d{4})(\d{2})(\d{2})", filename)
        if match_strict:
            prefix, annee, mois, jour = match_strict.groups()
            return annee, mois_fr.get(mois, mois)

        print(f"[{filename}] Impossible d'extraire la date du nom. Fichier non classé.")
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

            annee, mois = get_date_from_file(filepath, filename, mode_tri)

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
                    f"Doublon - Fichier déplacé : {os.path.join(destination_doublon_mois, filename)}"
                )
            else:
                shutil.move(filepath, destination_filepath)
                print(f"Fichier déplacé : {destination_filepath}")

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

    print(f"\nTerminé ! {fichiers_traites} fichiers médias traités.")


def main():
    print(
        r"""
   _____           _  _____                 _     _             
  / ____|         | |/ ____|               | |   (_)            
 | (___  _   _  __| | (___   ___  _ __ _ __| |_   _ _ __   __ _ 
  \___ \| | | |/ _` |\___ \ / _ \| '__| '__| __| | | '_ \ / _` |
  ____) | |_| | (_| |____) | (_) | |  | |  | |_ _| | | | | (_| |
 |_____/ \__,_|\__,_|_____/ \___/|_|  |_|   \__(_)_|_| |_|\__, |
                                                            __/ |
                                                           |___/ 
    """
    )

    config = charger_config()

    if config:
        print("\nUne configuration existante a été trouvée :")
        print(f"  - Dossier source      : {config.get('source')}")
        print(f"  - Dossier destination : {config.get('destination')}")
        print(f"  - Mode de tri         : {config.get('mode_tri')}")
        print("\nQue voulez-vous faire ?")
        print("1) Utiliser la configuration présente")
        print("2) Recommencer la configuration / From scratch")

        choix = ""
        while choix not in ["1", "2"]:
            choix = input("Votre choix (1 ou 2) : ").strip()

        if choix == "2":
            config = configurer()
    else:
        print("\nAucune configuration trouvée. Création d'une nouvelle configuration.")
        config = configurer()

    print("\n--- Lancement du tri ---")
    copier_coller_media(config)


if __name__ == "__main__":
    main()
