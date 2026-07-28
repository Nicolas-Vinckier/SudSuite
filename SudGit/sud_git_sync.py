import os
import sys
import json
import subprocess
import time
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed


# Détection initiale du support UTF-8
def get_emojis(use_utf8=True):
    return {
        "BACK": "🔙" if use_utf8 else "[BACK]",
        "BOX": "📦" if use_utf8 else "[BOX]",
        "BYE": "👋" if use_utf8 else "[BYE]",
        "CHART": "📊" if use_utf8 else "[STATS]",
        "COMPASS": "🧭" if use_utf8 else "[MENU]",
        "DOOR": "🚪" if use_utf8 else "[EXIT]",
        "ERROR": "❌" if use_utf8 else "[ERROR]",
        "FOLDER": "📂" if use_utf8 else "[DIR]",
        "GEAR": "⚙️" if use_utf8 else "[CFG]",
        "HOURGLASS": "⏳" if use_utf8 else "[WAIT]",
        "INBOX": "📥" if use_utf8 else "[IN]",
        "LIGHTNING": "⚡" if use_utf8 else "[SPEED]",
        "MINUS": "➖" if use_utf8 else "[-]",
        "OUTBOX": "📤" if use_utf8 else "[OUT]",
        "PENCIL": "✏️" if use_utf8 else "[EDIT]",
        "PLUS": "➕" if use_utf8 else "[+]",
        "POINTER": "👉" if use_utf8 else ">",
        "RETURN": "↩️" if use_utf8 else "[RETURN]",
        "ROCKET": "🚀" if use_utf8 else "[START]",
        "SCALES": "⚖️" if use_utf8 else "[COMPARE]",
        "SEARCH": "🔍" if use_utf8 else "[SCAN]",
        "SHUFFLE": "🔀" if use_utf8 else "[SWITCH]",
        "STOPWATCH": "⏱️" if use_utf8 else "[TIME]",
        "SUCCESS": "✅" if use_utf8 else "[OK]",
        "SYNC": "🔄" if use_utf8 else "[SYNC]",
        "TARGET": "🎯" if use_utf8 else "[TARGET]",
        "WARN": "⚠️" if use_utf8 else "[WARN]",
    }


_UTF8_SYSTEM = (getattr(sys.stdout, "encoding", "") or "").lower() == "utf-8"
E = get_emojis(_UTF8_SYSTEM)


def safe_print(msg, end="\n"):
    """Imprime un message en gérant les erreurs d'encodage sur Windows."""
    try:
        print(msg, end=end)
    except UnicodeEncodeError:
        clean_msg = str(msg).encode("ascii", "ignore").decode("ascii")
        print(clean_msg, end=end)


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "sud_git_config.json")

# Verrou global pour l'affichage (évite l'entrelacement entre threads)
_print_lock = threading.Lock()


def afficher_en_tete():
    safe_print(
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
    global E
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
                if "use_emojis" not in config:
                    config["use_emojis"] = _UTF8_SYSTEM

                # Mise à jour globale des émojis selon la config
                E = get_emojis(config["use_emojis"])

                return config
        except json.JSONDecodeError:
            safe_print(
                f"{E['ERROR']} \033[91mErreur de lecture de la configuration. Fichier corrompu.\033[0m"
            )
            return {"depots": [], "intervalle": 60, "parallelisme": 5}
    return {"depots": [], "intervalle": 60, "parallelisme": 5}


def sauvegarder_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        safe_print(f"{E['ERROR']} \033[91mErreur lors de la sauvegarde : {e}\033[0m")


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


def detecter_branche_depot(repo_path):
    """
    Détecte la branche par défaut d'un dépôt Git local.
    Recherche d'abord la branche pointeur distante (origin/HEAD),
    puis les branches distantes/locales standards (SudBranch, main, master...),
    et enfin la branche courante.
    """
    if not os.path.exists(repo_path) or not os.path.isdir(
        os.path.join(repo_path, ".git")
    ):
        return "Inaccessible"

    # 1. Branche par défaut distante via origin/HEAD (ex: refs/remotes/origin/HEAD -> origin/SudBranch ou origin/main)
    ok, out = executer_commande_git(
        repo_path, ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"]
    )
    if ok and out and out.strip():
        ref = out.strip()
        if ref.startswith("origin/"):
            return ref[7:]
        return ref

    ok, out = executer_commande_git(
        repo_path, ["rev-parse", "--abbrev-ref", "origin/HEAD"]
    )
    if ok and out and out.strip() and out.strip() != "origin/HEAD":
        ref = out.strip()
        if ref.startswith("origin/"):
            return ref[7:]
        return ref

    # 2. Recherche parmi les branches distantes (git branch -r) pour les noms standards
    ok, out = executer_commande_git(repo_path, ["branch", "-r"])
    if ok and out and out.strip():
        r_branches = [
            line.strip().split("/")[-1]
            for line in out.splitlines()
            if line.strip() and "->" not in line
        ]
        for pref in ["SudBranch", "main", "master", "dev", "develop"]:
            if pref in r_branches:
                return pref

    # 3. Recherche parmi les branches locales pour les noms standards
    ok, out = executer_commande_git(repo_path, ["branch", "--format=%(refname:short)"])
    if ok and out and out.strip():
        l_branches = [b.strip() for b in out.splitlines() if b.strip()]
        for pref in ["SudBranch", "main", "master", "dev", "develop"]:
            if pref in l_branches:
                return pref

    # 4. Branche courante (checked out)
    ok, out = executer_commande_git(repo_path, ["branch", "--show-current"])
    if ok and out and out.strip():
        return out.strip()

    return "Inconnue"


def configurer_depots():
    global E
    config = charger_config()
    while True:
        safe_print(f"\n\033[93m--- {E['GEAR']}  Configuration des dépôts ---\033[0m")
        depots = config.get("depots", [])
        if not depots:
            safe_print(f"{E['FOLDER']} Aucun dépôt configuré pour le moment.")
        else:
            # Affichage en tableau pour une meilleure lisibilité
            safe_print(
                "\033[96m┌────┬──────────────────────────────────────────────────┬────────────────────┐"
            )
            safe_print(
                "│ ID │ Dossier / Chemin                                 │ Branche            │"
            )
            safe_print(
                "├────┼──────────────────────────────────────────────────┼────────────────────┤\033[0m"
            )
            for i, d in enumerate(depots, 1):
                chemin = d["chemin"]
                # Tronquer le chemin s'il est trop long pour tenir dans le tableau
                if len(chemin) > 48:
                    display_path = "..." + chemin[-45:]
                else:
                    display_path = chemin

                branche_config = d.get("branche")
                if branche_config:
                    visible_text = branche_config
                    if len(visible_text) > 18:
                        visible_text = visible_text[:15] + "..."
                    padding = " " * (18 - len(visible_text))
                    display_branche = f"\033[96m{visible_text}\033[0m{padding}"
                else:
                    branche_detectee = detecter_branche_depot(chemin)
                    visible_text = f"{branche_detectee} (auto)"
                    if len(visible_text) > 18:
                        max_b_len = 18 - 7
                        if max_b_len > 3:
                            branche_detectee = branche_detectee[: max_b_len - 3] + "..."
                        else:
                            branche_detectee = branche_detectee[:max_b_len]
                        visible_text = f"{branche_detectee} (auto)"
                    padding = " " * (18 - len(visible_text))
                    display_branche = (
                        f"\033[96m{branche_detectee}\033[90m (auto)\033[0m{padding}"
                    )

                safe_print(
                    f"\033[96m│\033[0m {i:<2} \033[96m│\033[0m {display_path:<48} \033[96m│\033[0m {display_branche} \033[96m│\033[0m"
                )
            safe_print(
                "\033[96m└────┴──────────────────────────────────────────────────┴────────────────────┘\033[0m"
            )
            safe_print(
                f"{E['STOPWATCH']}  Intervalle actuel : \033[93m{config.get('intervalle', 60)} secondes\033[0m"
            )
            safe_print(
                f"{E['LIGHTNING']} Parallélisme actuel : \033[93m{config.get('parallelisme', 5)} thread(s) simultané(s)\033[0m"
            )
            status_emojis = (
                "\033[92mActivés\033[0m"
                if config.get("use_emojis")
                else "\033[91mDésactivés (Mode Texte)\033[0m"
            )
            safe_print(f"{E['SHUFFLE']} Émojis : {status_emojis}")

        safe_print("\nOptions :")
        safe_print(f"1. {E['PLUS']} Ajouter un dossier")
        safe_print(f"2. {E['MINUS']} Supprimer un dossier")
        safe_print(f"3. {E['SEARCH']} Scan de dossier parent")
        safe_print(f"4. {E['PENCIL']}  Modifier la branche d'un dossier")
        safe_print(f"5. {E['STOPWATCH']}  Modifier l'intervalle de sync (Mode Continu)")
        safe_print(f"6. {E['LIGHTNING']} Modifier le nombre de dépôts en parallèle")
        safe_print(f"7. {E['SHUFFLE']} Basculer Émojis / Texte seul")
        safe_print(f"0. {E['RETURN']} Retour au menu principal")

        choix = input(f"\n{E['POINTER']} Votre choix (0-7) : ").strip()

        if choix == "1":
            chemin = input(
                "Chemin absolu ou relatif du dépôt git (0 pour annuler) : "
            ).strip()
            if not chemin or chemin == "0":
                continue

            chemin_abs = os.path.abspath(chemin)
            if not os.path.exists(chemin_abs):
                safe_print(f"{E['ERROR']} \033[91mCe chemin n'existe pas.\033[0m")
                continue
            if not os.path.isdir(os.path.join(chemin_abs, ".git")):
                safe_print(
                    f"{E['WARN']}  \033[93mCe dossier ne semble pas être un dépôt git valide (aucun dossier .git trouvé).\033[0m\nVoulez-vous tout de même l'ajouter ? (o/n)"
                )
                if input("-> ").strip().lower() != "o":
                    continue

            branche = input(
                "Branche cible (laissez vide pour auto-détection) : "
            ).strip()

            # Vérification de doublons
            for d in depots:
                if d["chemin"] == chemin_abs:
                    safe_print(
                        f"{E['WARN']}  \033[93mCe chemin est déjà configuré, modification de la branche...\033[0m"
                    )
                    d["branche"] = branche
                    break
            else:
                depots.append({"chemin": chemin_abs, "branche": branche})

            config["depots"] = depots
            sauvegarder_config(config)
            safe_print(f"{E['SUCCESS']} \033[92mDépôt configuré avec succès.\033[0m")

        elif choix == "2":
            if not depots:
                safe_print(f"{E['WARN']}  \033[93mAucun dépôt à supprimer.\033[0m")
                continue
            try:
                entree = input(
                    f"Numéro du dépôt à supprimer (1-{len(depots)}, 0 pour annuler) : "
                ).strip()
                if entree == "0":
                    continue
                idx = int(entree) - 1
                if 0 <= idx < len(depots):
                    supprime = depots.pop(idx)
                    config["depots"] = depots
                    sauvegarder_config(config)
                    safe_print(
                        f"{E['SUCCESS']} \033[92mDépôt supprimé : {supprime['chemin']}\033[0m"
                    )
                else:
                    safe_print(f"{E['ERROR']} \033[91mNuméro invalide.\033[0m")
            except ValueError:
                safe_print(f"{E['ERROR']} \033[91mEntrée invalide.\033[0m")

        elif choix == "3":
            parent = input(
                "Dossier parent à scanner (ex: C:/Dev/Projets, 0 pour annuler) : "
            ).strip()
            if not parent or parent == "0":
                continue

            parent_abs = os.path.abspath(parent)
            if not os.path.isdir(parent_abs):
                safe_print(
                    f"{E['ERROR']} \033[91mLe chemin spécifié n'est pas un dossier valide.\033[0m"
                )
                continue

            safe_print(f"{E['HOURGLASS']} Scan de {parent_abs} en cours...")
            trouves = 0
            ajoutes = 0
            enleves = 0

            try:
                parent_norm = os.path.normcase(parent_abs)
                dossiers_presents = []
                dossiers_presents_norm = set()

                for item in os.listdir(parent_abs):
                    item_path = os.path.abspath(os.path.join(parent_abs, item))
                    if os.path.isdir(item_path) and os.path.isdir(
                        os.path.join(item_path, ".git")
                    ):
                        dossiers_presents.append(item_path)
                        dossiers_presents_norm.add(os.path.normcase(item_path))

                trouves = len(dossiers_presents)

                # Ajout des nouveaux dépôts Git trouvés
                existing_depots_norm = {
                    os.path.normcase(os.path.abspath(d["chemin"])) for d in depots
                }
                for item_path in dossiers_presents:
                    if os.path.normcase(item_path) not in existing_depots_norm:
                        depots.append({"chemin": item_path, "branche": ""})
                        ajoutes += 1

                # Suppression des dépôts sous ce dossier parent qui n'y sont plus
                nouveau_depots = []
                for d in depots:
                    d_abs = os.path.abspath(d["chemin"])
                    d_parent_norm = os.path.normcase(os.path.dirname(d_abs))
                    if d_parent_norm == parent_norm:
                        if os.path.normcase(d_abs) in dossiers_presents_norm:
                            nouveau_depots.append(d)
                        else:
                            enleves += 1
                    else:
                        nouveau_depots.append(d)

                depots = nouveau_depots

                if ajoutes > 0 or enleves > 0:
                    config["depots"] = depots
                    sauvegarder_config(config)

                safe_print(f"{E['SUCCESS']} \033[92mScan terminé !\033[0m")
                safe_print(f"   {E['SEARCH']} Dépôts Git détectés : {trouves}")
                safe_print(f"   {E['PLUS']} Nouveaux dépôts ajoutés : {ajoutes}")
                safe_print(f"   {E['MINUS']} Dépôts retirés (non trouvés) : {enleves}")
            except Exception as e:
                safe_print(f"{E['ERROR']} \033[91mErreur lors du scan : {e}\033[0m")

        elif choix == "4":
            if not depots:
                safe_print(f"{E['WARN']}  \033[93mAucun dépôt à modifier.\033[0m")
                continue
            try:
                entree = input(
                    f"Numéro du dépôt à modifier (1-{len(depots)}, 0 pour annuler) : "
                ).strip()
                if entree == "0":
                    continue
                idx = int(entree) - 1
                if 0 <= idx < len(depots):
                    nouvelle_branche = input(
                        "Nouvelle branche cible (laissez vide pour auto-détection) : "
                    ).strip()
                    depots[idx]["branche"] = nouvelle_branche
                    config["depots"] = depots
                    sauvegarder_config(config)
                    safe_print(f"{E['SUCCESS']} \033[92mBranche mise à jour.\033[0m")
                else:
                    safe_print(f"{E['ERROR']} \033[91mNuméro invalide.\033[0m")
            except ValueError:
                safe_print(f"{E['ERROR']} \033[91mEntrée invalide.\033[0m")

        elif choix == "5":
            try:
                entree = input(
                    "Entrez le nouvel intervalle en secondes (min 10, 0 pour annuler) : "
                ).strip()
                if entree == "0":
                    continue
                nouveau_temps = int(entree)
                if nouveau_temps < 10:
                    safe_print(
                        f"{E['WARN']}  \033[93mIntervalle trop court (min 10s pour éviter le spam).\033[0m"
                    )
                    nouveau_temps = 10
                config["intervalle"] = nouveau_temps
                sauvegarder_config(config)
                safe_print(
                    f"{E['SUCCESS']} \033[92mIntervalle mis à jour à {nouveau_temps}s.\033[0m"
                )
            except ValueError:
                safe_print(
                    f"{E['ERROR']} \033[91mEntrée invalide, veuillez saisir un nombre entier.\033[0m"
                )

        elif choix == "6":
            try:
                entree = input(
                    "Nombre de dépôts à traiter en parallèle (1 = séquentiel, défaut 5, 0 pour annuler) : "
                ).strip()
                if entree == "0":
                    continue
                val = int(entree)
                if val < 1:
                    safe_print(
                        f"{E['WARN']}  \033[93mValeur trop basse, minimum 1.\033[0m"
                    )
                    val = 1
                config["parallelisme"] = val
                sauvegarder_config(config)
                safe_print(
                    f"{E['SUCCESS']} \033[92mParallélisme mis à jour à {val} thread(s).\033[0m"
                )
            except ValueError:
                safe_print(
                    f"{E['ERROR']} \033[91mEntrée invalide, veuillez saisir un nombre entier.\033[0m"
                )

        elif choix == "7":
            config["use_emojis"] = not config.get("use_emojis", True)
            sauvegarder_config(config)
            # Rafraîchir E immédiatement
            E = get_emojis(config["use_emojis"])
            safe_print(
                f"{E['SUCCESS']} Mode {'Émojis' if config['use_emojis'] else 'Texte'} activé."
            )

        elif choix == "0":
            break
        else:
            safe_print(f"{E['ERROR']} \033[91mOption invalide.\033[0m")


def push_custom_stash(repo_path):
    """
    Met en stash les modifications locales (staged + unstaged + untracked)
    avec un identifiant unique pour ne pas impacter les autres stashes.
    Retourne (succès, stash_tag).
    """
    ok_status, out_status = executer_commande_git(repo_path, ["status", "--porcelain"])
    if not ok_status or not out_status.strip():
        # Rien à stasher
        return True, None

    stash_tag = f"sudgit-stash-{uuid.uuid4().hex[:8]}"
    ok_stash, out_stash = executer_commande_git(
        repo_path, ["stash", "push", "-u", "-m", stash_tag]
    )
    if not ok_stash:
        return False, None

    ok_list, out_list = executer_commande_git(repo_path, ["stash", "list"])
    if ok_list and stash_tag in out_list:
        return True, stash_tag

    return False, None


def pop_custom_stash(repo_path, stash_tag):
    """
    Restaure exactement le stash correspondant à stash_tag par son index stash@{N}.
    """
    if not stash_tag:
        return True, "Aucun stash à restaurer."

    ok_list, out_list = executer_commande_git(repo_path, ["stash", "list"])
    if not ok_list or not out_list:
        return False, "Impossible d'obtenir la liste des stashes."

    target_ref = None
    for line in out_list.splitlines():
        if stash_tag in line:
            # Format classique: "stash@{0}: On branch: sudgit-stash-1a2b3c4d"
            target_ref = line.split(":")[0].strip()
            break

    if not target_ref:
        return False, f"Stash introuvable ({stash_tag})."

    ok_pop, out_pop = executer_commande_git(repo_path, ["stash", "pop", target_ref])
    return ok_pop, out_pop


def syncer_depot(d):
    """
    Synchronise un dépôt git avec sa branche cible (par défaut ou configurée) :
    1. Détecte la branche courante (ex: local-security-layer) et la branche cible (ex: SudBranch).
    2. Exécute git fetch --prune.
    3. Si la branche cible est déjà à jour avec origin/branche_cible, s'arrête là (pas de stash ni de checkout inutile).
    4. Si la branche cible a des nouveautés :
       - Crée un stash nommé sudgit-stash-<uuid> pour les modifications locales non enregistrées.
       - Bascule sur la branche cible (checkout SudBranch) si nécessaire.
       - Effectue le pull de la branche cible.
       - Repasse sur la branche d'origine (checkout local-security-layer).
       - Restaure le stash spécifique (stash pop stash@{N}).
    """
    logs = []
    chemin = d["chemin"]
    logs.append(f"\n{E['FOLDER']} \033[1mTraitement de : {chemin}\033[0m")

    if not os.path.exists(chemin) or not os.path.isdir(os.path.join(chemin, ".git")):
        logs.append(
            f"  {E['ERROR']} \033[91mErreur : Dossier non-Git ou inexistant.\033[0m"
        )
        return False, logs

    # 1. Détection de la branche actuellement extraite
    ok_bc, branche_courante = executer_commande_git(
        chemin, ["branch", "--show-current"]
    )
    if not ok_bc or not branche_courante:
        ok_head, out_head = executer_commande_git(
            chemin, ["rev-parse", "--abbrev-ref", "HEAD"]
        )
        branche_courante = out_head if (ok_head and out_head != "HEAD") else "HEAD"

    # 2. Détermination de la branche cible à synchroniser
    branche_cible = d.get("branche")
    if not branche_cible:
        branche_cible = detecter_branche_depot(chemin)

    logs.append(
        f"  {E['TARGET']} Branche de travail : \033[96m{branche_courante}\033[0m | Branche cible : \033[96m{branche_cible}\033[0m"
    )

    # 3. Git Fetch avec Prune
    logs.append(
        f"  {E['HOURGLASS']} Récupération de l'état distant (git fetch --prune)..."
    )
    f_succes, f_out = executer_commande_git(chemin, ["fetch", "--prune"])
    if not f_succes:
        logs.append(f"  {E['ERROR']} \033[91mErreur de fetch : {f_out}\033[0m")
        return False, logs

    # 4. Comparaison de la branche cible avec son remote
    ok_local, rev_local = executer_commande_git(chemin, ["rev-parse", branche_cible])
    ok_remote, rev_remote = executer_commande_git(
        chemin, ["rev-parse", f"origin/{branche_cible}"]
    )

    if ok_local and ok_remote and rev_local == rev_remote:
        logs.append(
            f"  {E['SUCCESS']} \033[92mBranche \033[96m{branche_cible}\033[92m déjà à jour.\033[0m"
        )
        return True, logs

    logs.append(
        f"  {E['INBOX']} \033[93mMises à jour distantes détectées sur \033[96m{branche_cible}\033[0m..."
    )

    # 5. Stash personnalisé des modifications locales (si présentes)
    stash_ok, stash_tag = push_custom_stash(chemin)
    if not stash_ok:
        logs.append(
            f"  {E['ERROR']} \033[91mErreur lors du stash des modifications locales.\033[0m"
        )
        return False, logs

    if stash_tag:
        logs.append(
            f"  {E['BOX']} \033[93mModifications locales sauvegardées (Stash ID: {stash_tag})...\033[0m"
        )

    sur_bonne_branche = branche_courante == branche_cible
    checkout_effectue = False

    # 6. Checkout vers la branche cible si nécessaire
    if not sur_bonne_branche:
        logs.append(
            f"  {E['SHUFFLE']} Passage sur la branche \033[96m{branche_cible}\033[0m..."
        )
        co_ok, co_out = executer_commande_git(chemin, ["checkout", branche_cible])
        if not co_ok:
            logs.append(
                f"  {E['ERROR']} \033[91mErreur lors du checkout vers {branche_cible} : {co_out}\033[0m"
            )
            if stash_tag:
                pop_custom_stash(chemin, stash_tag)
            return False, logs
        checkout_effectue = True

    # 7. Git Pull sur la branche cible
    logs.append(f"  {E['SYNC']} Synchronisation (git pull origin {branche_cible})...")
    pull_ok, pull_out = executer_commande_git(chemin, ["pull", "origin", branche_cible])

    resultat_ok = False
    if pull_ok:
        logs.append(
            f"  {E['SUCCESS']} \033[92mBranche \033[96m{branche_cible}\033[92m mise à jour avec succès.\033[0m"
        )
        resultat_ok = True
    else:
        logs.append(
            f"  {E['ERROR']} \033[91mErreur lors du pull de {branche_cible} : {pull_out}\033[0m"
        )

    # 8. Retour sur la branche d'origine si on avait changé de branche
    if checkout_effectue:
        logs.append(
            f"  {E['SHUFFLE']} Retour sur la branche initiale (\033[96m{branche_courante}\033[0m)..."
        )
        co_back_ok, co_back_out = executer_commande_git(
            chemin, ["checkout", branche_courante]
        )
        if not co_back_ok:
            logs.append(
                f"  {E['WARN']}  \033[93mAvertissement lors du retour sur {branche_courante} : {co_back_out}\033[0m"
            )

    # 9. Restauration du stash unique créé pour cette opération
    if stash_tag:
        logs.append(
            f"  {E['OUTBOX']} \033[93mRestauration du stash {stash_tag}...\033[0m"
        )
        pop_ok, pop_msg = pop_custom_stash(chemin, stash_tag)
        if pop_ok:
            logs.append(
                f"  {E['SUCCESS']} \033[92mModifications locales restaurées avec succès.\033[0m"
            )
        else:
            logs.append(
                f"  {E['WARN']}  \033[93mAvertissement lors du stash pop : {pop_msg}\033[0m"
            )

    return resultat_ok, logs


def lancer_sync():
    config = charger_config()
    depots = config.get("depots", [])

    if not depots:
        safe_print(
            f"\n{E['WARN']}  \033[93mAucun dépôt configuré. Veuillez configurer des dépôts dans le menu 2.\033[0m"
        )
        return

    parallelisme = config.get("parallelisme", 5)
    workers = min(parallelisme, len(depots))

    safe_print(
        f"\n\033[94m{E['ROCKET']} Lancement de la synchronisation (GitSync) — {workers} thread(s) en parallèle...\033[0m"
    )

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
                    safe_print(ligne)
            if ok:
                succes += 1
            else:
                echecs += 1

    duree = time.time() - debut
    safe_print("\n" + "=" * 45)
    safe_print(f"{E['CHART']} \033[1mBilan final de la GitSync :\033[0m")
    safe_print(
        f"  {E['SUCCESS']} \033[92mDépôts à jour ou mis à jour : {succes}\033[0m"
    )
    safe_print(f"  {E['ERROR']} \033[91mDépôts en échec ou ignorés  : {echecs}\033[0m")
    safe_print(f"  {E['STOPWATCH']}  Durée totale : \033[93m{duree:.1f}s\033[0m")
    safe_print("=" * 45)


def lancer_sync_continu():
    config = charger_config()
    depots = config.get("depots", [])

    if not depots:
        safe_print(
            f"\n{E['WARN']}  \033[93mAucun dépôt configuré. Veuillez configurer des dépôts dans le menu 3.\033[0m"
        )
        return

    intervalle = config.get("intervalle", 60)
    safe_print(
        f"\n\033[94m{E['SYNC']} Mode de synchronisation continue activé (intervalle : {intervalle}s).\033[0m"
    )
    safe_print("\033[93mAppuyez sur Ctrl+C pour arrêter et quitter.\033[0m\n")

    try:
        iteration = 1
        while True:
            safe_print(f"\n\033[95m--- {E['SYNC']} Itération n°{iteration} ---\033[0m")
            lancer_sync()
            safe_print(
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
            safe_print(f"\n\033[95m--- {E['COMPASS']} Menu Principal ---\033[0m")
            safe_print(f"1. {E['ROCKET']} Lancement unique")
            safe_print(f"2. {E['SYNC']} Lancement continu ({intervalle}s)")
            safe_print(f"3. {E['GEAR']}  Configurer les dossiers à vérifier")
            safe_print(f"0. {E['DOOR']} Quitter")
            safe_print(f"\n\033[90m[Parallélisme : {parallelisme} thread(s)]\033[0m")

            choix = input(f"\n{E['POINTER']} Votre choix (0-3) : ").strip()

            if choix == "1":
                lancer_sync()
            elif choix == "2":
                lancer_sync_continu()
            elif choix == "3":
                configurer_depots()
            elif choix == "0":
                safe_print(
                    f"\n{E['BYE']} \033[96mMerci d'avoir utilisé SudGit Sync. À bientôt !\033[0m\n"
                )
                break
            else:
                safe_print(
                    f"{E['ERROR']} \033[91mChoix invalide, veuillez réessayer.\033[0m"
                )

        except KeyboardInterrupt:
            safe_print(
                f"\n\n{E['WARN']}  \033[93mInterruption détectée (Ctrl+C). Fermeture de SudGit Sync.\033[0m\n"
            )
            sys.exit(0)
        except Exception as e:
            safe_print(
                f"\n{E['ERROR']} \033[91mUne erreur inattendue s'est produite : {e}\033[0m\n"
            )


if __name__ == "__main__":
    main()
