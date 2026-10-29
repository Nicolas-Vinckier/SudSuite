import tempfile
import unittest
from pathlib import Path

from SudSecurity.integrity import create_manifest, load_manifest, verify_manifest


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "data"
        self.root.mkdir()
        (self.root / "a.txt").write_text("alpha", encoding="utf-8")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "b.txt").write_text("beta", encoding="utf-8")
        self.manifest = Path(self.temp.name) / "manifest.json"

    def test_untouched_folder_verifies_cleanly(self):
        create_manifest(self.root, self.manifest)
        report = verify_manifest(self.manifest, self.root)
        self.assertEqual(len(report.issues), 0)

    def test_modification_deletion_and_addition_are_reported(self):
        create_manifest(self.root, self.manifest)
        (self.root / "a.txt").write_text("ALPHA!", encoding="utf-8")
        (self.root / "sub" / "b.txt").unlink()
        (self.root / "nouveau.txt").write_text("x", encoding="utf-8")

        report = verify_manifest(self.manifest, self.root)

        self.assertEqual(len(report.issues), 3)

    def test_manifest_with_unsafe_path_is_refused(self):
        create_manifest(self.root, self.manifest)
        content = self.manifest.read_text(encoding="utf-8").replace("a.txt", "../evil.txt")
        self.manifest.write_text(content, encoding="utf-8")
        with self.assertRaises(ValueError):
            verify_manifest(self.manifest, self.root)

    def test_manifest_round_trip(self):
        create_manifest(self.root, self.manifest)
        self.assertIn("files", load_manifest(self.manifest))


if __name__ == "__main__":
    unittest.main()
