"""Point d'entrée de SudSecurity : chiffrement et intégrité."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SudCore.launcher import Entry, launch

TITLE = "SudSecurity"
DESCRIPTION = "Chiffrement et contrôle d'intégrité"

TOOLS: tuple[Entry, ...] = (
    Entry("vault", "Sud Vault Sync", "chiffre et synchronise vers le cloud", "SudSecurity.sud_vault_sync"),
    Entry("integrity", "Sud Integrity", "manifeste et vérification d'empreintes", "SudSecurity.sud_integrity"),
)


def main(argv: Sequence[str] | None = None) -> int:
    return launch(TITLE, TOOLS, argv)


if __name__ == "__main__":
    sys.exit(main())
