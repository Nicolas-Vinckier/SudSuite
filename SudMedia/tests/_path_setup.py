"""Initialisation des imports quand un test est lancé comme un script."""

import sys
from pathlib import Path


def add_project_root() -> None:
    project_root = Path(__file__).resolve().parents[2]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)
