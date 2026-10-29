import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cryptography.fernet import Fernet

from SudSecurity.vault import (
    MAGIC,
    VaultError,
    create_key,
    decrypt_file,
    default_key_path,
    encrypt_file,
    load_key,
)
from SudSecurity.vault import crypto


class VaultCryptoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fernet = Fernet(Fernet.generate_key())

    def roundtrip(self, data: bytes, chunk_size: int | None = None) -> bytes:
        source = self.root / "clair.bin"
        encrypted = self.root / "clair.bin.sud"
        restored = self.root / "restaure.bin"
        source.write_bytes(data)
        if chunk_size:
            with mock.patch.object(crypto, "CHUNK_SIZE", chunk_size):
                encrypt_file(self.fernet, source, encrypted)
        else:
            encrypt_file(self.fernet, source, encrypted)
        self.assertTrue(encrypted.read_bytes().startswith(MAGIC))
        decrypt_file(self.fernet, encrypted, restored)
        return restored.read_bytes()

    def test_roundtrip_empty_small_and_multi_chunk_files(self):
        self.assertEqual(self.roundtrip(b""), b"")
        self.assertEqual(self.roundtrip(b"bonjour"), b"bonjour")
        payload = os.urandom(1000)
        self.assertEqual(self.roundtrip(payload, chunk_size=100), payload)
        exact = os.urandom(300)
        self.assertEqual(self.roundtrip(exact, chunk_size=100), exact)

    def test_wrong_key_is_rejected(self):
        source = self.root / "a.txt"
        source.write_text("secret", encoding="utf-8")
        encrypted = self.root / "a.txt.sud"
        encrypt_file(self.fernet, source, encrypted)
        other = Fernet(Fernet.generate_key())
        with self.assertRaises(VaultError):
            decrypt_file(other, encrypted, self.root / "out.txt")
        self.assertFalse((self.root / "out.txt").exists())

    def test_truncation_and_reordering_are_detected(self):
        source = self.root / "a.bin"
        source.write_bytes(os.urandom(500))
        encrypted = self.root / "a.bin.sud"
        with mock.patch.object(crypto, "CHUNK_SIZE", 100):
            encrypt_file(self.fernet, source, encrypted)
        blob = encrypted.read_bytes()

        truncated = self.root / "truncated.sud"
        truncated.write_bytes(blob[: len(blob) // 2])
        with self.assertRaises(VaultError):
            decrypt_file(self.fernet, truncated, self.root / "t.out")

        body = blob[len(MAGIC):]
        blocks = []
        while body:
            length = int.from_bytes(body[:4], "big")
            blocks.append(body[: 4 + length])
            body = body[4 + length:]
        reordered = self.root / "reordered.sud"
        reordered.write_bytes(MAGIC + blocks[1] + blocks[0] + b"".join(blocks[2:]))
        with self.assertRaises(VaultError):
            decrypt_file(self.fernet, reordered, self.root / "r.out")

    def test_failed_decryption_leaves_no_partial_file(self):
        bad = self.root / "bad.sud"
        bad.write_bytes(b"pas un fichier chiffre")
        target = self.root / "bad.out"
        with self.assertRaises(VaultError):
            decrypt_file(self.fernet, bad, target)
        self.assertFalse(target.exists())
        self.assertEqual([p.name for p in self.root.glob(".*.tmp")], [])


class VaultKeyTests(unittest.TestCase):
    def test_create_then_load_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sous" / "sudsuite.key"
            self.assertIsNone(load_key(path))
            created = create_key(path)
            loaded = load_key(path)
            self.assertEqual(loaded.decrypt(created.encrypt(b"x")), b"x")
            with self.assertRaises(VaultError):
                create_key(path)

    def test_invalid_key_file_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sudsuite.key"
            path.write_bytes(b"pas une cle")
            with self.assertRaises(VaultError):
                load_key(path)

    def test_key_path_can_be_overridden_and_lives_outside_the_repository(self):
        with mock.patch.dict(os.environ, {crypto.KEY_ENV_VARIABLE: "~/custom.key"}):
            self.assertEqual(default_key_path(), Path("~/custom.key").expanduser())
        with mock.patch.dict(os.environ, clear=False):
            os.environ.pop(crypto.KEY_ENV_VARIABLE, None)
            self.assertEqual(default_key_path().parent.name, ".sudsuite")


if __name__ == "__main__":
    unittest.main()
