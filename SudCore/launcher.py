"""Menu et exécution communs aux points d'entrée de SudSuite."""

from __future__ import annotations

import runpy
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .console import configure_console_output


@dataclass(frozen=True)
class Entry:
    """Un élément lançable : un outil (module) ou un sous-menu (fonction)."""

    key: str
    title: str
    description: str
    module: str | None = None
    action: Callable[[Sequence[str]], int] | None = None


def run_module(module: str, argv: Sequence[str] = ()) -> int:
    """Exécute un module comme ``python -m`` avec ``argv`` et renvoie son code."""
    previous_argv = sys.argv
    sys.argv = [module, *argv]
    try:
        runpy.run_module(module, run_name="__main__", alter_sys=True)
    except SystemExit as stop:
        code = stop.code
        return code if isinstance(code, int) else (0 if code is None else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Interrompu.")
        return 130
    finally:
        sys.argv = previous_argv
    return 0


def run_entry(entry: Entry, argv: Sequence[str] = ()) -> int:
    if entry.action is not None:
        return entry.action(argv)
    if entry.module is None:
        raise ValueError(f"L'entrée '{entry.key}' n'a ni module ni action.")
    return run_module(entry.module, argv)


def find_entry(entries: Sequence[Entry], token: str) -> Entry | None:
    """Retrouve une entrée par son numéro (1-based) ou par sa clé."""
    token = token.strip().lower()
    for number, entry in enumerate(entries, 1):
        if token in {str(number), entry.key.lower()}:
            return entry
    return None


def print_catalog(title: str, entries: Sequence[Entry]) -> None:
    print(f"\n=== {title} ===")
    for number, entry in enumerate(entries, 1):
        print(f"  {number:>2}. {entry.key:<12} {entry.title} - {entry.description}")


def launch(
    title: str,
    entries: Sequence[Entry],
    argv: Sequence[str] | None = None,
    *,
    banner: str = "",
) -> int:
    """Point d'entrée générique.

    Sans argument : menu interactif. Avec ``<outil> [args...]`` : lance l'outil
    directement. ``--list`` affiche le catalogue.
    """
    configure_console_output()
    args = list(sys.argv[1:] if argv is None else argv)

    if args and args[0] in {"-l", "--list", "-h", "--help"}:
        print("Usage : <lanceur> [outil [arguments...]]   |   --list")
        print_catalog(title, entries)
        return 0
    if args:
        entry = find_entry(entries, args[0])
        if entry is None:
            print(f"❌ Outil inconnu : {args[0]}")
            print_catalog(title, entries)
            return 2
        return run_entry(entry, args[1:])

    if banner:
        print(banner)
    while True:
        print_catalog(title, entries)
        print("   0. Quitter")
        try:
            choice = input("\n👉 Votre choix : ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 À bientôt !")
            return 0
        if choice.lower() in {"0", "q", "quit", "exit", ""}:
            print("👋 À bientôt !")
            return 0
        entry = find_entry(entries, choice)
        if entry is None:
            print("❌ Choix invalide.")
            continue
        run_entry(entry)
