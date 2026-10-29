import tempfile
import unittest
from pathlib import Path
from unittest import mock

from SudCore import (
    atomic_write_json,
    atomic_write_text,
    clean_input_path,
    collect_files,
    hash_file,
    paths_overlap,
    unique_path,
)


class FilesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_collect_files_filters_ignored_directories_and_extensions(self):
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules" / "x.txt").write_text("x")
        (self.root / "a.TXT").write_text("a")
        (self.root / "b.md").write_text("b")
        found = collect_files([f'"{self.root}"'], extensions=["txt"])
        self.assertEqual([p.name for p in found], ["a.TXT"])

    def test_unique_path_and_clean_input_path(self):
        target = self.root / "f.txt"
        target.write_text("1")
        self.assertEqual(unique_path(target).name, "f_2.txt")
        self.assertEqual(clean_input_path(" 'a b' "), "a b")

    def test_paths_overlap(self):
        (self.root / "sub").mkdir()
        self.assertTrue(paths_overlap(self.root, self.root / "sub"))
        self.assertFalse(paths_overlap(self.root / "sub", self.root / "other"))

    def test_atomic_writes_replace_content_and_leave_no_temporary_file(self):
        target = self.root / "d" / "data.json"
        atomic_write_json(target, {"b": 1, "a": "é"})
        atomic_write_json(target, {"a": 2})
        self.assertIn('"a": 2', target.read_text(encoding="utf-8"))
        self.assertEqual(list(target.parent.glob(".*.tmp")), [])

    def test_failed_atomic_write_keeps_previous_content(self):
        target = self.root / "t.txt"
        atomic_write_text(target, "avant")
        with mock.patch("SudCore.files.os.replace", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                atomic_write_text(target, "après")
        self.assertEqual(target.read_text(encoding="utf-8"), "avant")
        self.assertEqual(list(self.root.glob(".*.tmp")), [])

    def test_hash_file_matches_sha256(self):
        target = self.root / "h.txt"
        target.write_bytes(b"abc")
        self.assertEqual(
            hash_file(target),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        )


if __name__ == "__main__":
    unittest.main()
