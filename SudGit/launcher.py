"""Point d'entrée de SudGit : synchronisation de dépôts et de dossiers."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SudCore.launcher import Entry, launch

TITLE = "SudGit"
DESCRIPTION = "Synchronisation de dépôts Git et de dossiers"

TOOLS: tuple[Entry, ...] = (
    Entry("git", "SudGit Sync", "synchronise vos dépôts Git", "SudGit.sud_git_sync"),
    Entry("folder", "SudFolder Sync", "synchronise deux dossiers", "SudGit.sud_folder_sync"),
)


def main(argv: Sequence[str] | None = None) -> int:
    return launch(TITLE, TOOLS, argv)


if __name__ == "__main__":
    sys.exit(main())
