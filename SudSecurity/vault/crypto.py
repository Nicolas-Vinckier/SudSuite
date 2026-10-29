"""Chiffrement par blocs et gestion de la clé de Sud Vault.

Format d'un fichier ``.sud`` : l'en-tête ``MAGIC`` puis une suite de jetons Fernet
précédés de leur longueur (4 octets, big-endian). Chaque bloc clair contient son
numéro, un drapeau « dernier bloc » puis les données : un bloc supprimé, réordonné
ou une troncature est donc détecté au déchiffrement. Les fichiers sont traités par
blocs de ``CHUNK_SIZE`` sans jamais être chargés entièrement en mémoire.
"""

from __future__ import annotations

import os
import struct
import subprocess
import sys
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from SudCore.files import atomic_write_bytes

MAGIC = b"SUDVAULT1\n"
CHUNK_SIZE = 4 * 1024 * 1024
KEY_ENV_VARIABLE = "SUDSUITE_KEY"
KEY_FILENAME = "sudsuite.key"

_LENGTH = struct.Struct(">I")
_BLOCK_HEADER = struct.Struct(">QB")


class VaultError(RuntimeError):
    """Fichier chiffré invalide, altéré ou clé incorrecte."""


def default_key_path() -> Path:
    """Chemin de la clé : variable ``SUDSUITE_KEY`` ou ``~/.sudsuite/sudsuite.key``."""
    override = os.environ.get(KEY_ENV_VARIABLE)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".sudsuite" / KEY_FILENAME


def restrict_permissions(path: Path) -> None:
    """Réserve le fichier à l'utilisateur courant (chmod 600 / ACL Windows)."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    if sys.platform == "win32":
        username = os.environ.get("USERNAME")
        if username:
            subprocess.run(
                ["icacls", str(path), "/inheritance:r", "/grant:r", f"{username}:F"],
                capture_output=True,
                check=False,
            )


def load_key(path: Path | None = None) -> Fernet | None:
    """Charge la clé existante, ou renvoie ``None`` si elle est absente."""
    key_path = path or default_key_path()
    if not key_path.is_file():
        return None
    try:
        return Fernet(key_path.read_bytes().strip())
    except ValueError as error:
        raise VaultError(f"Clé invalide dans {key_path} : {error}") from error


def create_key(path: Path | None = None) -> Fernet:
    """Génère une nouvelle clé, écrite atomiquement avec des droits restreints."""
    key_path = path or default_key_path()
    if key_path.exists():
        raise VaultError(f"Une clé existe déjà : {key_path}")
    key = Fernet.generate_key()
    atomic_write_bytes(key_path, lambda stream: stream.write(key), mode=0o600)
    restrict_permissions(key_path)
    return Fernet(key)


def _read_exact(stream, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise VaultError("Fichier chiffré tronqué.")
    return data


def encrypt_file(fernet: Fernet, source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> int:
    """Chiffre ``source`` vers ``destination`` (atomique) et renvoie la taille écrite."""

    def write(output) -> None:
        output.write(MAGIC)
        with open(source, "rb") as reader:
            index = 0
            chunk = reader.read(CHUNK_SIZE)
            while True:
                following = reader.read(CHUNK_SIZE) if chunk else b""
                final = not following
                token = fernet.encrypt(_BLOCK_HEADER.pack(index, final) + chunk)
                output.write(_LENGTH.pack(len(token)))
                output.write(token)
                if final:
                    return
                index += 1
                chunk, following = following, b""

    atomic_write_bytes(destination, write)
    return os.path.getsize(destination)


def decrypt_file(fernet: Fernet, source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> int:
    """Déchiffre ``source`` vers ``destination`` (atomique) et renvoie la taille claire."""

    def write(output) -> None:
        with open(source, "rb") as reader:
            if reader.read(len(MAGIC)) != MAGIC:
                raise VaultError("Format de fichier chiffré non reconnu.")
            expected = 0
            while True:
                (length,) = _LENGTH.unpack(_read_exact(reader, _LENGTH.size))
                try:
                    plain = fernet.decrypt(_read_exact(reader, length))
                except InvalidToken as error:
                    raise VaultError("Clé incorrecte ou fichier altéré.") from error
                index, final = _BLOCK_HEADER.unpack(plain[: _BLOCK_HEADER.size])
                if index != expected:
                    raise VaultError("Blocs chiffrés manquants ou réordonnés.")
                output.write(plain[_BLOCK_HEADER.size :])
                expected += 1
                if final:
                    if reader.read(1):
                        raise VaultError("Données inattendues après le dernier bloc.")
                    return

    atomic_write_bytes(destination, write)
    return os.path.getsize(destination)
