import os
import sys
import time
import heapq
import argparse
from pathlib import Path
from dataclasses import dataclass, field


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


@dataclass
class FolderNode:
    path: Path
    size: int = 0
    file_count: int = 0
    dir_count: int = 0
    children: list = field(default_factory=list)


def clean_input_path(value):
    return value.strip().replace('"', "").replace("'", "")


def format_size(size_in_bytes):
    for unit in ["O", "Ko", "Mo", "Go"]:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} To"


def non_negative_int(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("La valeur doit être un nombre entier.")

    if number < 0:
        raise argparse.ArgumentTypeError("La valeur doit être supérieure ou égale à 0.")

    return number


def build_argument_parser():
    parser = argparse.ArgumentParser(
        prog="sudweight.py",
        description="Analyse le poids d'un dossier et affiche une arborescence par taille.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=r"""
Exemples :

  Questionnaire complet :
    python sudweight.py

  Dossier prérempli, puis questionnaire pour les options :
    python sudweight.py "C:\Users\Moi\Documents"

  Analyse directe avec profondeur 2, top 10 fichiers, exclusions activées :
    python sudweight.py "C:\Users\Moi\Documents" --depth 2 --top 10 --exclude

  Analyse directe sans questionnaire avec les valeurs par défaut :
    python sudweight.py "C:\Users\Moi\Documents" --no-interactive

  Analyse du dossier courant, profondeur 1, top 20 fichiers :
    python sudweight.py . --depth 1 --top 20 --no-exclude

  Profondeur illimitée explicitement :
    python sudweight.py "C:\Users\Moi\Documents" --no-depth-limit --top 10 --exclude
"""
    )

    parser.add_argument(
        "dossier",
        nargs="?",
        help="Dossier à analyser, chemin absolu ou relatif."
    )

    parser.add_argument(
        "-p",
        "--dossier",
        dest="dossier_option",
        help="Dossier à analyser, chemin absolu ou relatif. Alternative à l'argument positionnel."
    )

    depth_group = parser.add_mutually_exclusive_group()

    depth_group.add_argument(
        "-d",
        "--depth",
        "--max-depth",
        dest="depth",
        type=non_negative_int,
        default=None,
        help=(
            "Nombre max de descentes affichées.\n"
            "0 = dossier racine seulement.\n"
            "1 = dossiers directs seulement.\n"
            "2 = dossiers directs + leurs sous-dossiers.\n"
            "Si absent, le script demande la valeur en mode interactif."
        )
    )

    depth_group.add_argument(
        "--no-depth-limit",
        action="store_true",
        help="Désactive la limite de profondeur. Équivaut à Entrée dans le questionnaire."
    )

    parser.add_argument(
        "-t",
        "--top",
        dest="top",
        type=non_negative_int,
        default=None,
        help=(
            "Affiche le top X des fichiers les plus lourds.\n"
            "0 = désactivé.\n"
            "Si absent, le script demande la valeur en mode interactif."
        )
    )

    exclusion_group = parser.add_mutually_exclusive_group()

    exclusion_group.add_argument(
        "--exclude",
        dest="use_exclusions",
        action="store_true",
        help="Active l'exclusion des dossiers/fichiers techniques."
    )

    exclusion_group.add_argument(
        "--no-exclude",
        dest="use_exclusions",
        action="store_false",
        help="Désactive l'exclusion des dossiers/fichiers techniques."
    )

    parser.set_defaults(use_exclusions=None)

    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help=(
            "Ne pose aucune question.\n"
            "Les options absentes prennent leurs valeurs par défaut :\n"
            "- profondeur illimitée ;\n"
            "- top fichiers désactivé ;\n"
            "- exclusions désactivées."
        )
    )

    return parser


def parse_cli_args():
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.dossier and args.dossier_option:
        if clean_input_path(args.dossier) != clean_input_path(args.dossier_option):
            parser.error(
                "Le dossier est indiqué deux fois avec deux valeurs différentes. "
                "Utilisez soit l'argument positionnel, soit --dossier."
            )

    return args


def ask_optional_int(prompt, min_value=0):
    while True:
        value = input(prompt).strip()

        if value == "":
            return None

        try:
            number = int(value)

            if number < min_value:
                print(f"[Erreur] La valeur doit être supérieure ou égale à {min_value}.")
                continue

            return number

        except ValueError:
            print("[Erreur] Veuillez entrer un nombre entier valide.")


def ask_yes_no(prompt, default=True):
    suffix = "(O/n)" if default else "(o/N)"

    while True:
        value = input(f"{prompt} {suffix} : ").strip().lower()

        if value == "":
            return default

        if value in ["o", "oui", "y", "yes"]:
            return True

        if value in ["n", "non", "no"]:
            return False

        print("[Erreur] Répondez par oui ou non.")


def safe_relative_path(path, root_path):
    try:
        return path.relative_to(root_path)
    except ValueError:
        return path


def add_to_top_files(heap, limit, file_size, file_path, root_path):
    if not limit or limit <= 0:
        return

    relative_path = safe_relative_path(file_path, root_path)

    item = (
        file_size,
        str(relative_path),
        str(file_path),
    )

    if len(heap) < limit:
        heapq.heappush(heap, item)
    else:
        if file_size > heap[0][0]:
            heapq.heapreplace(heap, item)


def scan_folder(folder_path, root_path, excluded_names, top_files_heap, top_files_limit, errors, stats):
    node = FolderNode(path=folder_path)
    stats["folders_scanned"] += 1

    try:
        with os.scandir(folder_path) as entries:
            for entry in entries:
                entry_path = Path(entry.path)

                try:
                    if entry.name in excluded_names:
                        continue

                    # On ignore les liens symboliques pour éviter les boucles infinies.
                    if entry.is_symlink():
                        continue

                    if entry.is_dir(follow_symlinks=False):
                        child_node = scan_folder(
                            folder_path=entry_path,
                            root_path=root_path,
                            excluded_names=excluded_names,
                            top_files_heap=top_files_heap,
                            top_files_limit=top_files_limit,
                            errors=errors,
                            stats=stats,
                        )

                        node.children.append(child_node)
                        node.size += child_node.size
                        node.file_count += child_node.file_count
                        node.dir_count += 1 + child_node.dir_count

                    elif entry.is_file(follow_symlinks=False):
                        file_size = entry.stat(follow_symlinks=False).st_size

                        node.size += file_size
                        node.file_count += 1
                        stats["files_scanned"] += 1

                        add_to_top_files(
                            heap=top_files_heap,
                            limit=top_files_limit,
                            file_size=file_size,
                            file_path=entry_path,
                            root_path=root_path,
                        )

                        if stats["files_scanned"] % 500 == 0:
                            print(
                                f"\r[Analyse] {stats['folders_scanned']} dossiers | "
                                f"{stats['files_scanned']} fichiers",
                                end="",
                            )

                except PermissionError:
                    errors.append(f"Accès refusé : {entry_path}")

                except FileNotFoundError:
                    errors.append(f"Introuvable pendant l'analyse : {entry_path}")

                except OSError as e:
                    errors.append(f"Erreur système sur {entry_path} : {e}")

    except PermissionError:
        errors.append(f"Accès refusé : {folder_path}")

    except FileNotFoundError:
        errors.append(f"Dossier introuvable pendant l'analyse : {folder_path}")

    except OSError as e:
        errors.append(f"Erreur système sur {folder_path} : {e}")

    node.children.sort(key=lambda child: child.size, reverse=True)

    return node


def format_folder_line(node, parent_size=None):
    if parent_size and parent_size > 0:
        percent = (node.size / parent_size) * 100
        percent_text = f" | {percent:.1f}% du parent"
    else:
        percent_text = ""

    return (
        f"{node.path.name}/ "
        f"[{format_size(node.size)} | "
        f"{node.file_count} fichier(s) | "
        f"{node.dir_count} dossier(s){percent_text}]"
    )


def print_tree(root_node, max_depth):
    print("\n" + "=" * 70)
    print("📊 ARBORESCENCE DES POIDS")
    print("=" * 70)

    print(
        f"{root_node.path} "
        f"[{format_size(root_node.size)} | "
        f"{root_node.file_count} fichier(s) | "
        f"{root_node.dir_count} dossier(s)]"
    )

    def print_children(node, prefix="", current_depth=0):
        if max_depth is not None and current_depth >= max_depth:
            return

        child_count = len(node.children)

        for index, child in enumerate(node.children):
            is_last = index == child_count - 1
            connector = "└── " if is_last else "├── "
            extension = "    " if is_last else "│   "

            print(prefix + connector + format_folder_line(child, node.size))

            print_children(
                node=child,
                prefix=prefix + extension,
                current_depth=current_depth + 1,
            )

    print_children(root_node)


def print_top_files(top_files_heap, top_files_limit):
    if not top_files_limit or top_files_limit <= 0:
        return

    print("\n" + "=" * 70)
    print(f"🏋️ TOP {top_files_limit} DES FICHIERS LES PLUS LOURDS")
    print("=" * 70)

    if not top_files_heap:
        print("Aucun fichier trouvé.")
        return

    top_files = sorted(top_files_heap, key=lambda item: item[0], reverse=True)

    for index, item in enumerate(top_files, start=1):
        file_size, relative_path, absolute_path = item

        print(f"{index:>3}. {format_size(file_size):>12}  {relative_path}")


def print_errors(errors):
    if not errors:
        return

    print("\n" + "=" * 70)
    print("⚠️  ÉLÉMENTS NON ANALYSÉS")
    print("=" * 70)

    max_errors_to_show = 20

    for error in errors[:max_errors_to_show]:
        print(f"- {error}")

    remaining = len(errors) - max_errors_to_show

    if remaining > 0:
        print(f"... et {remaining} autre(s) erreur(s).")


def resolve_target_folder(args):
    target_input = args.dossier_option or args.dossier

    if target_input:
        target_input = clean_input_path(target_input)
    elif args.no_interactive:
        print("[Erreur] Aucun dossier indiqué.")
        print("Exemple : python sudweight.py \"C:\\Users\\Moi\\Documents\" --no-interactive")
        return None
    else:
        target_input = clean_input_path(
            input("📂 Dossier à analyser (chemin absolu ou relatif) : ")
        )

    if not target_input:
        print("[Erreur] Aucun dossier indiqué.")
        return None

    target_folder = Path(target_input).expanduser()

    if not target_folder.is_absolute():
        target_folder = (Path.cwd() / target_folder).resolve()
    else:
        target_folder = target_folder.resolve()

    if not target_folder.exists():
        print(f"[Erreur] Le chemin n'existe pas : {target_folder}")
        return None

    if not target_folder.is_dir():
        print(f"[Erreur] Ce chemin n'est pas un dossier : {target_folder}")
        return None

    return target_folder


def resolve_max_depth(args):
    if args.no_depth_limit:
        return None

    if args.depth is not None:
        return args.depth

    if args.no_interactive:
        return None

    return ask_optional_int(
        "Nombre max de descente "
        "(Entrée = aucune limite, 1 = dossiers directs seulement) : ",
        min_value=0,
    )


def resolve_top_files_limit(args):
    if args.top is not None:
        if args.top == 0:
            return None
        return args.top

    if args.no_interactive:
        return None

    top_files_limit = ask_optional_int(
        "Afficher le top X des fichiers les plus lourds "
        "(Entrée ou 0 = ne pas afficher) : ",
        min_value=0,
    )

    if top_files_limit == 0:
        return None

    return top_files_limit


def resolve_exclusions(args):
    if args.use_exclusions is not None:
        use_exclusions = args.use_exclusions
    elif args.no_interactive:
        use_exclusions = False
    else:
        use_exclusions = ask_yes_no(
            "Ignorer les dossiers/fichiers techniques "
            f"({', '.join(list(EXCLUDE_PATTERNS)[:4])}...)",
            default=False,
        )

    return EXCLUDE_PATTERNS if use_exclusions else set()


def print_banner():
    print(
        r"""
 ____            ___        __   _       _     _   
/ ___| _   _  __| \ \      / /__(_) __ _| |__ | |_ 
\___ \| | | |/ _` |\ \ /\ / / _ \ |/ _` | '_ \| __|
 ___) | |_| | (_| | \ V  V /  __/ | (_| | | | | |_ 
|____/ \__,_|\__,_|  \_/\_/ \___|_|\__, |_| |_|\__|
                                   |___/           
        """
    )


def analyze_folder_weights(args):
    print_banner()

    target_folder = resolve_target_folder(args)

    if target_folder is None:
        return

    need_param_header = not args.no_interactive and (
        args.depth is None
        and not args.no_depth_limit
        or args.top is None
        or args.use_exclusions is None
    )

    if need_param_header:
        print("\n" + "=" * 70)
        print("⚙️  PARAMÈTRES D'ANALYSE")
        print("=" * 70)

    max_depth = resolve_max_depth(args)
    top_files_limit = resolve_top_files_limit(args)
    excluded_names = resolve_exclusions(args)

    print("\n" + "=" * 70)
    print("🔎 ANALYSE EN COURS")
    print("=" * 70)
    print(f"[Dossier] {target_folder}")

    if max_depth is None:
        print("[Descente] Aucune limite")
    else:
        print(f"[Descente] {max_depth}")

    if top_files_limit:
        print(f"[Top fichiers] Top {top_files_limit}")
    else:
        print("[Top fichiers] Désactivé")

    if excluded_names:
        print(f"[Exclusions] {', '.join(excluded_names)}")
    else:
        print("[Exclusions] Aucune")

    start_time = time.time()

    errors = []
    top_files_heap = []

    stats = {
        "folders_scanned": 0,
        "files_scanned": 0,
    }

    root_node = scan_folder(
        folder_path=target_folder,
        root_path=target_folder,
        excluded_names=excluded_names,
        top_files_heap=top_files_heap,
        top_files_limit=top_files_limit,
        errors=errors,
        stats=stats,
    )

    end_time = time.time()

    print(
        f"\r[Analyse] {stats['folders_scanned']} dossiers | "
        f"{stats['files_scanned']} fichiers"
    )

    print_tree(root_node, max_depth)
    print_top_files(top_files_heap, top_files_limit)
    print_errors(errors)

    print("\n" + "=" * 70)
    print("✅ ANALYSE TERMINÉE")
    print("=" * 70)
    print(f"📂 Dossier analysé     : {target_folder}")
    print(f"📦 Taille totale       : {format_size(root_node.size)}")
    print(f"📄 Nombre de fichiers  : {root_node.file_count}")
    print(f"📁 Nombre de dossiers  : {root_node.dir_count}")
    print(f"⚠️  Erreurs rencontrées : {len(errors)}")
    print(f"⏱️  Temps écoulé        : {end_time - start_time:.2f} secondes")
    print("=" * 70)


if __name__ == "__main__":
    try:
        cli_args = parse_cli_args()
        analyze_folder_weights(cli_args)
    except KeyboardInterrupt:
        print("\n\n[Interruption] Analyse annulée par l'utilisateur.")
        sys.exit(0)