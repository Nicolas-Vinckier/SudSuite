"""Interface en ligne de commande de Sud Integrity."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SudSecurity.integrity import create_manifest, verify_manifest


def configure_console_output() -> None:
    if sys.platform == "win32":
        os.system("")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8")
            except (AttributeError, LookupError, OSError):
                pass


def print_banner() -> None:
    print(r"""
  ____            _   ___       _                  _ _
 / ___| _   _  __| | |_ _|_ __ | |_ ___  __ _ _ __(_) |_ _   _
 \___ \| | | |/ _` |  | || '_ \| __/ _ \/ _` | '__| | __| | | |
  ___) | |_| | (_| |  | || | | | ||  __/ (_| | |  | | |_| |_| |
 |____/ \__,_|\__,_| |___|_| |_|\__\___|\__, |_|  |_|\__|\__, |
                                         |___/             |___/
""")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crée ou vérifie un manifeste SHA-256.")
    subparsers = parser.add_subparsers(dest="command")
    create = subparsers.add_parser("create", help="Créer un manifeste")
    create.add_argument("root", nargs="?", help="Dossier à protéger")
    create.add_argument("-o", "--output", help="Chemin du manifeste JSON")
    verify = subparsers.add_parser("verify", help="Vérifier un manifeste")
    verify.add_argument("manifest", nargs="?", help="Manifeste JSON")
    verify.add_argument("--root", help="Dossier à contrôler")
    verify.add_argument("--ignore-new", action="store_true", help="Ne pas signaler les nouveaux fichiers")
    return parser


def _create(args) -> int:
    raw_root = args.root or input("📂 Dossier à protéger : ").strip().strip('"')
    root = Path(raw_root).expanduser().resolve()
    if not root.is_dir():
        print("❌ Dossier invalide.")
        return 2
    output = Path(args.output).expanduser() if args.output else root.parent / (
        f"{root.name}_Integrity_{datetime.now():%Y%m%d_%H%M%S}.json"
    )
    print("🔐 Calcul des empreintes SHA-256...")
    manifest = create_manifest(root, output)
    print(f"✅ {manifest['file_count']} fichier(s) enregistrés dans {output.resolve()}")
    return 0


def _verify(args) -> int:
    raw_manifest = args.manifest or input("📄 Manifeste à vérifier : ").strip().strip('"')
    manifest = Path(raw_manifest).expanduser().resolve()
    if not manifest.is_file():
        print("❌ Manifeste introuvable.")
        return 2
    raw_root = args.root or input("📂 Dossier à contrôler : ").strip().strip('"')
    print("🔎 Vérification des fichiers...")
    report = verify_manifest(manifest, raw_root, detect_unexpected=not args.ignore_new)
    print("\n" + "=" * 52)
    print(f"✅ Fichiers intacts : {report.unchanged_files}/{report.checked_files}")
    for kind, label in (
        ("missing", "Absents"),
        ("modified", "Modifiés"),
        ("unexpected", "Nouveaux"),
        ("error", "Erreurs"),
    ):
        issues = report.by_kind(kind)
        if issues:
            print(f"⚠️  {label} : {len(issues)}")
            for issue in issues:
                print(f"    • {issue.path} — {issue.detail}")
    print("=" * 52)
    print("✅ Intégrité confirmée." if report.valid else "❌ Des différences ont été détectées.")
    return 0 if report.valid else 1


def main(argv=None) -> int:
    configure_console_output()
    print_banner()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        choice = input("1. Créer un manifeste\n2. Vérifier un manifeste\nVotre choix : ").strip()
        return _verify(argparse.Namespace(manifest=None, root=None, ignore_new=False)) if choice == "2" else _create(argparse.Namespace(root=None, output=None))
    return _create(args) if args.command == "create" else _verify(args)


if __name__ == "__main__":
    raise SystemExit(main())
