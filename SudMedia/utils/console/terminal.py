"""Configuration du terminal et de la console."""

from __future__ import annotations

import os
import sys


def configure_console_output() -> None:
    """Configure la sortie UTF-8 quand le terminal courant le permet."""
    if sys.platform == "win32":
        # Active le traitement VT100 dans les consoles Windows compatibles.
        os.system("")

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (AttributeError, LookupError, OSError):
            # Une sortie redirigée ou remplacée (tests, IDE) n'est pas toujours
            # reconfigurable. L'outil reste utilisable avec son encodage courant.
            pass
