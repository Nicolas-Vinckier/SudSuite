import os
import sys
import json
import subprocess
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "sud_git_config.json")


def afficher_en_tete():
    print(
        r"""
 ____            _  ____ _ _   ____                   
/ ___| _   _  __| |/ ___(_) |_/ ___| _   _ _ __   ___ 
\___ \| | | |/ _` | |  _| | __\___ \| | | | '_ \ / __|
 ___) | |_| | (_| | |_| | | |_ ___) | |_| | | | | (__ 
|____/ \__,_|\__,_|\____|_|\__|____/ \__, |_| |_|\___|
                                     |___/            
    """
    )


def charger_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # Assurer la présence des clés par défaut
                if "depots" not in config:
                    config["depots"] = []
                if "intervalle" not in config:
                    config["intervalle"] = 60
                return config
        except json.JSONDecodeError:
            print(
                "❌ \033[91mErreur de lecture de la configuration. Fichier corrompu.\033[0m"
            )
            return {"depots": [], "intervalle": 60}
    return {"depots": [], "intervalle": 60}


def sauvegarder_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"❌ \033[91mErreur lors de la sauvegarde : {e}\033[0m")


def executer_commande_git(repo_path, commande):
    """
    Exécute une commande git dans le dépôt spécifié et retourne (succès, sortie)
    """
    try:
        if isinstance(commande, str):
            commande = commande.split()

        result = subprocess.run(
            ["git"] + commande,
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip()
    except Exception as e:
        return False, str(e)


def configurer_depots():
    config = charger_config()
    while True:
        print("\n\033[93m--- ⚙️  Configuration des dépôts ---\033[0m")
        depots = config.get("depots", [])
        if not depots:
            print("📂 Aucun dépôt configuré pour le moment.")
        else:
            # Affichage en tableau pour une meilleure lisibilité
            print(
                "\033[96m┌────┬──────────────────────────────────────────────────┬────────────────────┐"
            )
            print(
                "│ ID │ Dossier / Chemin                                 │ Branche            │"
            )
            print(
                "├────┼──────────────────────────────────────────────────┼────────────────────┤\033[0m"
            )
            for i, d in enumerate(depots, 1):
                chemin = d["chemin"]
                # Tronquer le chemin s'il est trop long pour tenir dans le tableau
                if len(chemin) > 48:
                    display_path = "..." + chemin[-45:]
                else:
                    display_path = chemin

                branche = d.get("branche") or "\033[90mAuto-détection\033[96m"
                print(
                    f"\033[96m│\033[0m {i:<2} \033[96m│\033[0m {display_path:<48} \033[96m│\033[0m {branche:<18} \033[96m│\033[0m"
                )
            print(
                "\033[96m└────┴──────────────────────────────────────────────────┴────────────────────┘\033[0m"
            )
            print(
                f"⏱️  Intervalle actuel : \033[93m{config.get('intervalle', 60)} secondes\033[0m"
            )

        print("\nOptions :")
        print("1. ➕ Ajouter un dossier individuel")
        print("2. 🔍 Scan de dossier parent (Ajout en masse)")
        print("3. ➖ Supprimer un dossier")
        print("4. ✏️  Modifier la branche d'un dossier")
        print("5. ⏱️  Modifier l'intervalle de sync (Mode Continu)")
        print("6. 🔙 Retour au menu principal")

        choix = input("\n👉 Votre choix (1-6) : ").strip()

        if choix == "1":
            chemin = input("Chemin absolu ou relatif du dépôt git : ").strip()
            if not chemin:
                continue

            chemin_abs = os.path.abspath(chemin)
            if not os.path.exists(chemin_abs):
                print("❌ \033[91mCe chemin n'existe pas.\033[0m")
                continue
            if not os.path.isdir(os.path.join(chemin_abs, ".git")):
                print(
                    "⚠️  \033[93mCe dossier ne semble pas être un dépôt git valide (aucun dossier .git trouvé).\033[0m\nVoulez-vous tout de même l'ajouter ? (o/n)"
                )
                if input("-> ").strip().lower() != "o":
                    continue

            branche = input(
                "Branche cible (laissez vide pour auto-détection) : "
            ).strip()

            # Vérification de doublons
            for d in depots:
                if d["chemin"] == chemin_abs:
                    print(
                        "⚠️  \033[93mCe chemin est déjà configuré, modification de la branche...\033[0m"
                    )
                    d["branche"] = branche
                    break
            else:
                depots.append({"chemin": chemin_abs, "branche": branche})

            config["depots"] = depots
            sauvegarder_config(config)
            print("✅ \033[92mDépôt configuré avec succès.\033[0m")

        elif choix == "2":
            parent = input("Dossier parent à scanner (ex: C:/Dev/Projets) : ").strip()
            if not parent:
                continue

            parent_abs = os.path.abspath(parent)
            if not os.path.isdir(parent_abs):
                print(
                    "❌ \033[91mLe chemin spécifié n'est pas un dossier valide.\033[0m"
                )
                continue

            print(f"⏳ Scan de {parent_abs} en cours...")
            trouves = 0
            ajoutes = 0

            try:
                for item in os.listdir(parent_abs):
                    item_path = os.path.join(parent_abs, item)
                    # On vérifie si c'est un dossier et s'il contient un .git
                    if os.path.isdir(item_path) and os.path.isdir(
                        os.path.join(item_path, ".git")
                    ):
                        trouves += 1
                        # On vérifie s'il est déjà dans la config
                        if not any(d["chemin"] == item_path for d in depots):
                            depots.append({"chemin": item_path, "branche": ""})
                            ajoutes += 1

                if trouves > 0:
                    config["depots"] = depots
                    sauvegarder_config(config)
                    print(f"✅ \033[92mScan terminé !\033[0m")
                    print(f"   🔍 Dépôts Git détectés : {trouves}")
                    print(f"   ➕ Nouveaux dépôts ajoutés : {ajoutes}")
                else:
                    print(
                        "⚠️  \033[93mAucun sous-dossier contenant un dépôt Git (.git) n'a été trouvé.\033[0m"
                    )
            except Exception as e:
                print(f"❌ \033[91mErreur lors du scan : {e}\033[0m")

        elif choix == "3":
            if not depots:
                print("⚠️  \033[93mAucun dépôt à supprimer.\033[0m")
                continue
            try:
                idx = (
                    int(input(f"Numéro du dépôt à supprimer (1-{len(depots)}) : ")) - 1
                )
                if 0 <= idx < len(depots):
                    supprime = depots.pop(idx)
                    config["depots"] = depots
                    sauvegarder_config(config)
                    print(f"✅ \033[92mDépôt supprimé : {supprime['chemin']}\033[0m")
                else:
                    print("❌ \033[91mNuméro invalide.\033[0m")
            except ValueError:
                print("❌ \033[91mEntrée invalide.\033[0m")

        elif choix == "4":
            if not depots:
                print("⚠️  \033[93mAucun dépôt à modifier.\033[0m")
                continue
            try:
                idx = int(input(f"Numéro du dépôt à modifier (1-{len(depots)}) : ")) - 1
                if 0 <= idx < len(depots):
                    nouvelle_branche = input(
                        "Nouvelle branche cible (laissez vide pour auto-détection) : "
                    ).strip()
                    depots[idx]["branche"] = nouvelle_branche
                    config["depots"] = depots
                    sauvegarder_config(config)
                    print("✅ \033[92mBranche mise à jour.\033[0m")
                else:
                    print("❌ \033[91mNuméro invalide.\033[0m")
            except ValueError:
                print("❌ \033[91mEntrée invalide.\033[0m")

        elif choix == "5":
            try:
                nouveau_temps = int(
                    input("Entrez le nouvel intervalle en secondes (min 10) : ")
                )
                if nouveau_temps < 10:
                    print(
                        "⚠️  \033[93mIntervalle trop court (min 10s pour éviter le spam).\033[0m"
                    )
                    nouveau_temps = 10
                config["intervalle"] = nouveau_temps
                sauvegarder_config(config)
                print(f"✅ \033[92mIntervalle mis à jour à {nouveau_temps}s.\033[0m")
            except ValueError:
                print(
                    "❌ \033[91mEntrée invalide, veuillez saisir un nombre entier.\033[0m"
                )

        elif choix == "6":
            break
        else:
            print("❌ \033[91mOption invalide.\033[0m")


def lancer_sync():
    config = charger_config()
    depots = config.get("depots", [])

    if not depots:
        print(
            "\n⚠️  \033[93mAucun dépôt configuré. Veuillez configurer des dépôts dans le menu 2.\033[0m"
        )
        return

    print("\n\033[94m🚀 Lancement de la synchronisation (GitSync)...\033[0m")

    succes = 0
    echecs = 0

    for d in depots:
        chemin = d["chemin"]
        print(f"\n📂 \033[1mTraitement de : {chemin}\033[0m")

        if not os.path.exists(chemin) or not os.path.isdir(
            os.path.join(chemin, ".git")
        ):
            print("  ❌ \033[91mErreur : Dossier non-Git ou inexistant.\033[0m")
            echecs += 1
            continue

        branche_cible = d.get("branche")

        # 1. Détection Automatique de Branche
        if not branche_cible:
            b_succes, b_out = executer_commande_git(
                chemin, ["branch", "--show-current"]
            )
            if b_succes and b_out:
                branche_cible = b_out
                print(
                    f"  🔍 Branche détectée automatiquement : \033[96m{branche_cible}\033[0m"
                )
            else:
                print(
                    "  ❌ \033[91mErreur : Impossible de détecter la branche courante. Dépôt initialisé mais sans commit ?\033[0m"
                )
                echecs += 1
                continue
        else:
            print(f"  🎯 Branche configurée : \033[96m{branche_cible}\033[0m")
            # Checkout de la branche cible si nécessaire
            checkout_succes, checkout_out = executer_commande_git(
                chemin, ["checkout", branche_cible]
            )
            if not checkout_succes:
                print(
                    f"  ❌ \033[91mErreur lors du checkout de la branche {branche_cible} : {checkout_out}\033[0m"
                )
                echecs += 1
                continue

        # 2. Git Fetch avec Prune
        print("  ⏳ Récupération de l'état distant (git fetch --prune)...")
        f_succes, f_out = executer_commande_git(chemin, ["fetch", "--prune"])
        if not f_succes:
            print(f"  ❌ \033[91mErreur de fetch : {f_out}\033[0m")
            echecs += 1
            continue

        # 3. Comparaison de l'état
        print("  ⚖️  Comparaison des états local et distant...")
        status_succes, status_out = executer_commande_git(chemin, ["status", "-uno"])

        if status_succes:
            out_lower = status_out.lower()
            if (
                "behind" in out_lower
                or "retard" in out_lower
                or "fast-forwarded" in out_lower
            ):
                # 4. Git Pull si maj trouvée
                print(
                    "  📥 \033[93mMises à jour distantes trouvées, exécution de git pull...\033[0m"
                )
                pull_succes, pull_out = executer_commande_git(chemin, ["pull"])
                if pull_succes:
                    print("  ✅ \033[92mMis à jour avec succès.\033[0m")
                    succes += 1
                else:
                    print(f"  ❌ \033[91mErreur lors du git pull : {pull_out}\033[0m")
                    echecs += 1
            elif "up to date" in out_lower or "à jour" in out_lower:
                print("  ✅ \033[92mDépôt déjà à jour.\033[0m")
                succes += 1
            else:
                # Fallback sécurisé en cas d'absence d'upstream branch configurée
                print(
                    "  ⚠️  \033[93mÉtat ambigu (pas d'upstream détecté), tentative de git pull origin...\033[0m"
                )
                pull_succes, pull_out = executer_commande_git(
                    chemin, ["pull", "origin", branche_cible]
                )
                if pull_succes:
                    if (
                        "already up to date" in pull_out.lower()
                        or "déjà à jour" in pull_out.lower()
                        or "already up-to-date" in pull_out.lower()
                    ):
                        print("  ✅ \033[92mDépôt déjà à jour.\033[0m")
                    else:
                        print("  ✅ \033[92mMis à jour avec succès.\033[0m")
                    succes += 1
                else:
                    print(
                        f"  ❌ \033[91mErreur lors du git pull (pas de remote 'origin' ou conflit ?) : {pull_out}\033[0m"
                    )
                    echecs += 1
        else:
            print(
                f"  ❌ \033[91mImpossible d'obtenir le statut git : {status_out}\033[0m"
            )
            echecs += 1

    print("\n" + "=" * 45)
    print("📊 \033[1mBilan final de la GitSync :\033[0m")
    print(f"  ✅ \033[92mDépôts à jour ou mis à jour : {succes}\033[0m")
    print(f"  ❌ \033[91mDépôts en échec ou ignorés  : {echecs}\033[0m")
    print("=" * 45)


def lancer_sync_continu():
    config = charger_config()
    depots = config.get("depots", [])

    if not depots:
        print(
            "\n⚠️  \033[93mAucun dépôt configuré. Veuillez configurer des dépôts dans le menu 3.\033[0m"
        )
        return

    intervalle = config.get("intervalle", 60)
    print(
        f"\n\033[94m🔄 Mode de synchronisation continue activé (intervalle : {intervalle}s).\033[0m"
    )
    print("\033[93mAppuyez sur Ctrl+C pour arrêter et quitter.\033[0m\n")

    try:
        iteration = 1
        while True:
            print(f"\n\033[95m--- 🔄 Itération n°{iteration} ---\033[0m")
            lancer_sync()
            print(
                f"\n\033[90m[Attente de {intervalle} secondes avant la prochaine vérification...]\033[0m"
            )
            time.sleep(intervalle)
            iteration += 1
    except KeyboardInterrupt:
        # On remonte l'exception pour qu'elle soit gérée par le main si besoin
        # ou on gère proprement ici pour revenir au menu (mais l'utilisateur a dit "quitter" souvent dans ce genre de script)
        raise


def main():
    # Activer les codes ANSI sur Windows
    if os.name == "nt":
        os.system("color")

    afficher_en_tete()

    while True:
        try:
            config = charger_config()
            intervalle = config.get("intervalle", 60)
            print("\n\033[95m--- 🧭 Menu Principal ---\033[0m")
            print("1. 🚀 Lancement unique")
            print(f"2. 🔄 Lancement continu ({intervalle}s)")
            print("3. ⚙️  Configurer les dossiers à vérifier")
            print("4. 🚪 Quitter")

            choix = input("\n👉 Votre choix (1-4) : ").strip()

            if choix == "1":
                lancer_sync()
            elif choix == "2":
                lancer_sync_continu()
            elif choix == "3":
                configurer_depots()
            elif choix == "4":
                print(
                    "\n👋 \033[96mMerci d'avoir utilisé SudGit Sync. À bientôt !\033[0m\n"
                )
                break
            else:
                print("❌ \033[91mChoix invalide, veuillez réessayer.\033[0m")

        except KeyboardInterrupt:
            print(
                "\n\n⚠️  \033[93mInterruption détectée (Ctrl+C). Fermeture de SudGit Sync.\033[0m\n"
            )
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ \033[91mUne erreur inattendue s'est produite : {e}\033[0m\n")


if __name__ == "__main__":
    main()
