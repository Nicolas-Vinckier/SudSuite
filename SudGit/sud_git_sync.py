import os
import sys
import json
import subprocess
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "sud_git_config.json")

# Verrou global pour l'affichage (évite l'entrelacement entre threads)
_print_lock = threading.Lock()


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
                if "parallelisme" not in config:
                    config["parallelisme"] = 5
                return config
        except json.JSONDecodeError:
            print(
                "❌ \033[91mErreur de lecture de la configuration. Fichier corrompu.\033[0m"
            )
            return {"depots": [], "intervalle": 60, "parallelisme": 5}
    return {"depots": [], "intervalle": 60, "parallelisme": 5}


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
            print(
                f"⚡ Parallélisme actuel : \033[93m{config.get('parallelisme', 5)} thread(s) simultané(s)\033[0m"
            )

        print("\nOptions :")
        print("1. ➕ Ajouter un dossier individuel")
        print("2. 🔍 Scan de dossier parent (Ajout en masse)")
        print("3. ➖ Supprimer un dossier")
        print("4. ✏️  Modifier la branche d'un dossier")
        print("5. ⏱️  Modifier l'intervalle de sync (Mode Continu)")
        print("6. ⚡ Modifier le nombre de dépôts en parallèle")
        print("7. 🔙 Retour au menu principal")

        choix = input("\n👉 Votre choix (1-7) : ").strip()

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
            try:
                val = int(
                    input(
                        "Nombre de dépôts à traiter en parallèle (1 = séquentiel, défaut 5) : "
                    )
                )
                if val < 1:
                    print("⚠️  \033[93mValeur trop basse, minimum 1.\033[0m")
                    val = 1
                config["parallelisme"] = val
                sauvegarder_config(config)
                print(f"✅ \033[92mParallélisme mis à jour à {val} thread(s).\033[0m")
            except ValueError:
                print(
                    "❌ \033[91mEntrée invalide, veuillez saisir un nombre entier.\033[0m"
                )

        elif choix == "7":
            break
        else:
            print("❌ \033[91mOption invalide.\033[0m")


def syncer_depot(d):
    """
    Synchronise un seul dépôt git et retourne (succes: bool, logs: list[str]).
    Cette fonction est conçue pour être exécutée en parallèle dans un thread.
    """
    logs = []
    chemin = d["chemin"]
    logs.append(f"\n📂 \033[1mTraitement de : {chemin}\033[0m")

    if not os.path.exists(chemin) or not os.path.isdir(
        os.path.join(chemin, ".git")
    ):
        logs.append("  ❌ \033[91mErreur : Dossier non-Git ou inexistant.\033[0m")
        return False, logs

    branche_cible = d.get("branche")

    # 1. Detection de la branche courante (toujours necessaire)
    bc_succes, branche_courante = executer_commande_git(
        chemin, ["branch", "--show-current"]
    )
    if not bc_succes or not branche_courante:
        logs.append("  ❌ \033[91mImpossible de détecter la branche courante.\033[0m")
        return False, logs

    # 2. Determination de la branche cible
    if not branche_cible:
        branche_cible = branche_courante
        logs.append(
            f"  🔍 Branche détectée automatiquement : \033[96m{branche_cible}\033[0m"
        )
    else:
        logs.append(f"  🎯 Branche configurée : \033[96m{branche_cible}\033[0m")

    sur_bonne_branche = branche_courante == branche_cible

    # 3. Git Fetch avec Prune
    logs.append("  ⏳ Récupération de l'état distant (git fetch --prune)...")
    f_succes, f_out = executer_commande_git(chemin, ["fetch", "--prune"])
    if not f_succes:
        logs.append(f"  ❌ \033[91mErreur de fetch : {f_out}\033[0m")
        return False, logs

    # 4. Comparaison de l'etat
    logs.append("  ⚖️  Comparaison des états local et distant...")
    status_succes, status_out = executer_commande_git(chemin, ["status", "-uno"])

    if not status_succes:
        logs.append(
            f"  ❌ \033[91mImpossible d'obtenir le statut git : {status_out}\033[0m"
        )
        return False, logs

    out_lower = status_out.lower()
    besoin_pull = (
        "behind" in out_lower
        or "retard" in out_lower
        or "fast-forwarded" in out_lower
    )
    deja_a_jour = "up to date" in out_lower or "à jour" in out_lower

    if deja_a_jour and not besoin_pull:
        logs.append("  ✅ \033[92mDépôt déjà à jour.\033[0m")
        return True, logs

    # Mode ambigu : pas d'upstream clairement configure
    pull_explicite = not besoin_pull and not deja_a_jour

    if pull_explicite:
        logs.append(
            "  ⚠️  \033[93mÉtat ambigu (pas d'upstream détecté), tentative de git pull origin...\033[0m"
        )

    # 5. Detection des fichiers modifies localement (staged + unstaged)
    _, fichiers_locaux_raw = executer_commande_git(
        chemin, ["diff", "--name-only", "HEAD"]
    )
    _, fichiers_staged_raw = executer_commande_git(
        chemin, ["diff", "--name-only", "--cached", "HEAD"]
    )
    fichiers_locaux = set(
        (fichiers_locaux_raw or "").splitlines()
        + (fichiers_staged_raw or "").splitlines()
    )
    fichiers_locaux = {f.strip() for f in fichiers_locaux if f.strip()}

    # 6. Detection des fichiers modifies cote distant
    _, fichiers_distants_raw = executer_commande_git(
        chemin, ["diff", "--name-only", f"HEAD...origin/{branche_cible}"]
    )
    fichiers_distants = {
        f.strip() for f in (fichiers_distants_raw or "").splitlines() if f.strip()
    }

    # 7. Verification des conflits potentiels
    conflits = fichiers_locaux & fichiers_distants

    stash_effectue = False
    checkout_effectue = False

    if fichiers_locaux:
        if conflits:
            logs.append(
                f"  ⚠️  \033[93mConflits potentiels sur {len(conflits)} fichier(s) — pull ignoré (gérez manuellement) :\033[0m"
            )
            for f in sorted(conflits):
                logs.append(f"      \033[91m⚡ {f}\033[0m")
            return False, logs
        else:
            logs.append(
                f"  📦 \033[93m{len(fichiers_locaux)} fichier(s) local/locaux sans conflit → git stash en cours...\033[0m"
            )
            stash_succes, stash_out = executer_commande_git(
                chemin, ["stash", "push", "-u", "-m", "sudgitsync-auto-stash"]
            )
            if not stash_succes:
                logs.append(f"  ❌ \033[91mErreur lors du git stash : {stash_out}\033[0m")
                return False, logs
            stash_effectue = True
            logs.append("  ✅ \033[92mChangements locaux mis en stash.\033[0m")

    # 8. Checkout vers la branche cible si on n'y est pas
    if not sur_bonne_branche:
        logs.append(
            f"  🔀 Branche courante (\033[96m{branche_courante}\033[0m) ≠ cible (\033[96m{branche_cible}\033[0m) — checkout en cours..."
        )
        checkout_succes, checkout_out = executer_commande_git(
            chemin, ["checkout", branche_cible]
        )
        if not checkout_succes:
            logs.append(f"  ❌ \033[91mErreur lors du checkout : {checkout_out}\033[0m")
            if stash_effectue:
                executer_commande_git(chemin, ["stash", "pop"])
                logs.append(
                    "  ↩️  \033[93mStash restauré suite à l'échec du checkout.\033[0m"
                )
            return False, logs
        checkout_effectue = True

    # 9. Git Pull
    logs.append(
        "  📥 \033[93mMises à jour distantes trouvées, exécution de git pull...\033[0m"
    )
    if pull_explicite:
        pull_succes, pull_out = executer_commande_git(
            chemin, ["pull", "origin", branche_cible]
        )
    else:
        pull_succes, pull_out = executer_commande_git(chemin, ["pull"])

    resultat_ok = False
    if pull_succes:
        if (
            "already up to date" in pull_out.lower()
            or "déjà à jour" in pull_out.lower()
            or "already up-to-date" in pull_out.lower()
        ):
            logs.append("  ✅ \033[92mDépôt déjà à jour.\033[0m")
        else:
            logs.append("  ✅ \033[92mMis à jour avec succès.\033[0m")
        resultat_ok = True
    else:
        logs.append(f"  ❌ \033[91mErreur lors du git pull : {pull_out}\033[0m")

    # 10. Retour sur la branche d'origine si on a switche
    if checkout_effectue:
        logs.append(
            f"  🔀 Retour sur la branche d'origine : \033[96m{branche_courante}\033[0m"
        )
        executer_commande_git(chemin, ["checkout", branche_courante])

    # 11. Restauration du stash
    if stash_effectue:
        logs.append(
            "  📤 \033[93mRestauration des changements locaux (git stash pop)...\033[0m"
        )
        pop_succes, pop_out = executer_commande_git(chemin, ["stash", "pop"])
        if pop_succes:
            logs.append("  ✅ \033[92mChangements locaux restaurés avec succès.\033[0m")
        else:
            logs.append(
                f"  ⚠️  \033[93mAvertissement lors du stash pop (conflit possible) : {pop_out}\033[0m"
            )

    return resultat_ok, logs


def lancer_sync():
    config = charger_config()
    depots = config.get("depots", [])

    if not depots:
        print(
            "\n⚠️  \033[93mAucun dépôt configuré. Veuillez configurer des dépôts dans le menu 2.\033[0m"
        )
        return

    parallelisme = config.get("parallelisme", 5)
    workers = min(parallelisme, len(depots))

    print(f"\n\033[94m🚀 Lancement de la synchronisation (GitSync) — {workers} thread(s) en parallèle...\033[0m")

    succes = 0
    echecs = 0
    debut = time.time()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(syncer_depot, d): d for d in depots}
        for future in as_completed(futures):
            ok, logs = future.result()
            # Impression atomique : tous les logs du dépôt d'un seul coup
            with _print_lock:
                for ligne in logs:
                    print(ligne)
            if ok:
                succes += 1
            else:
                echecs += 1

    duree = time.time() - debut
    print("\n" + "=" * 45)
    print("📊 \033[1mBilan final de la GitSync :\033[0m")
    print(f"  ✅ \033[92mDépôts à jour ou mis à jour : {succes}\033[0m")
    print(f"  ❌ \033[91mDépôts en échec ou ignorés  : {echecs}\033[0m")
    print(f"  ⏱️  Durée totale : \033[93m{duree:.1f}s\033[0m")
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
            parallelisme = config.get("parallelisme", 5)
            print("\n\033[95m--- 🧭 Menu Principal ---\033[0m")
            print("1. 🚀 Lancement unique")
            print(f"2. 🔄 Lancement continu ({intervalle}s)")
            print("3. ⚙️  Configurer les dossiers à vérifier")
            print("4. 🚪 Quitter")
            print(f"\n\033[90m[Parallélisme : {parallelisme} thread(s)]\033[0m")

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
