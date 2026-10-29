"""Point d'entrée unique de SudSuite.

    python sudsuite.py                      menu principal
    python sudsuite.py media                menu de SudMedia
    python sudsuite.py media compressor     lance directement un outil
    python sudsuite.py --list               liste les packages
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from SudCore.launcher import Entry, launch
from SudGit import launcher as git
from SudMedia import launcher as media
from SudSecurity import launcher as security

BANNER = r"""
  ____            _ ____        _ _
 / ___| _   _  __| / ___| _   _(_) |_ ___
 \___ \| | | |/ _` \___ \| | | | | __/ _ \
  ___) | |_| | (_| |___) | |_| | | ||  __/
 |____/ \__,_|\__,_|____/ \__,_|_|\__\___|
"""


def _package_entry(key: str, module) -> Entry:
    return Entry(
        key,
        module.TITLE,
        module.DESCRIPTION,
        action=lambda argv: module.main(list(argv)),
    )


PACKAGES: tuple[Entry, ...] = (
    _package_entry("media", media),
    _package_entry("git", git),
    _package_entry("security", security),
)


def main(argv: Sequence[str] | None = None) -> int:
    return launch("SudSuite", PACKAGES, argv, banner=BANNER)


if __name__ == "__main__":
    sys.exit(main())
