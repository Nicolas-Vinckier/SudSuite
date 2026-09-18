"""Lance toute la suite de tests SudMedia.

Exécuter depuis la racine du dépôt : ``py SudMedia/tests/test_all.py``.
Les nouveaux fichiers nommés ``test_*.py`` sont découverts automatiquement.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


def build_suite() -> unittest.TestSuite:
    """Découvre tous les fichiers de tests SudMedia, sauf ce lanceur."""
    tests_directory = Path(__file__).resolve().parent
    project_root = tests_directory.parents[1]
    return unittest.defaultTestLoader.discover(
        start_dir=tests_directory,
        pattern="test_*.py",
        top_level_dir=project_root,
    )


def main() -> int:
    result = unittest.TextTestRunner(verbosity=2).run(build_suite())
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
