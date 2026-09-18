"""Tests de la nouvelle architecture modulaire SudMedia.utils."""

import tempfile
import unittest
from pathlib import Path

try:
    from ._path_setup import add_project_root
except ImportError:
    from _path_setup import add_project_root

add_project_root()

from SudMedia.utils import (
    IMAGE_EXTENSIONS,
    HammingIndex,
    ProcessingStats,
    Progress,
    QualityAnalysis,
    SizeAnalysis,
    analyze_quality,
    analyze_size_change,
    folder_archive,
    atomic_write_json,
    atomic_write_text,
    clean_input_path,
    collect_files,
    collect_target_files,
    configure_console_output,
    console,
    content_hash,
    describe_backend,
    difference_hash,
    duplicate,
    filesystem,
    format_duration,
    format_size,
    format_size_short,
    hamming_distance,
    hash_file,
    hashing,
    image,
    metrics,
    normalize_quality,
    paths_overlap,
    progress,
    quarantine_duplicates,
    quarantine_files,
    reserve_output_path,
    resize_image,
    scan_duplicates,
    scan_folder,
    ocr,
    unique_available_path,
    unique_path,
    walk_filtered,
)
from SudMedia.utils.console import configure_console_output as console_cfg
from SudMedia.utils.duplicate import scan_duplicates as dupl_scan
from SudMedia.utils.filesystem import clean_input_path as fs_clean
from SudMedia.utils.hashing import hash_file as hash_f
from SudMedia.utils.image import resize_image as img_resize
from SudMedia.utils.metrics import format_size as met_format_size
from SudMedia.utils.progress import Progress as Prog
from SudMedia.utils.ocr import OCRDocument, OCRPage


class UtilsArchitectureTests(unittest.TestCase):
    def test_hub_reexports_and_submodules(self):
        self.assertTrue(callable(configure_console_output))
        self.assertTrue(callable(console_cfg))
        self.assertTrue(callable(fs_clean))
        self.assertTrue(callable(hash_f))
        self.assertTrue(callable(img_resize))
        self.assertTrue(callable(met_format_size))
        self.assertTrue(callable(dupl_scan))
        self.assertTrue(issubclass(Prog, Progress))

    def test_atomic_writes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            text_file = temp_path / "test.txt"
            json_file = temp_path / "test.json"

            atomic_write_text(text_file, "contenu test")
            self.assertEqual(text_file.read_text(encoding="utf-8"), "contenu test")

            atomic_write_json(json_file, {"cle": "valeur"})
            self.assertIn('"cle": "valeur"', json_file.read_text(encoding="utf-8"))

    def test_hashing_and_similarity(self):
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"data test hashing")
            temp_file_path = temp_file.name

        try:
            digest = content_hash(temp_file_path)
            self.assertEqual(len(digest), 64)
            self.assertEqual(hash_file(temp_file_path, "sha256"), digest)
        finally:
            Path(temp_file_path).unlink(missing_ok=True)

        self.assertEqual(hamming_distance(0b1010, 0b1001), 2)
        index = HammingIndex()
        index.add(0b1010, 1)
        index.add(0b1000, 2)
        self.assertEqual(index.neighbors(0b1010, 1), [1, 2])

    def test_generic_quarantine(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            file1 = root / "file1.txt"
            file2 = root / "file2.txt"
            file1.write_bytes(b"aaa")
            file2.write_bytes(b"aaa")

            quarantine_dir = root / "quarantaine"
            result = quarantine_files(
                [
                    {
                        "keeper": file1,
                        "duplicates": [{"path": file2, "size": 3, "kind": "exact"}],
                        "type": "exact",
                    }
                ],
                quarantine_dir,
            )

            self.assertEqual(result.released_bytes, 3)
            self.assertTrue((quarantine_dir / "manifest.json").exists())
            self.assertTrue(file1.exists())
            self.assertFalse(file2.exists())


if __name__ == "__main__":
    unittest.main()
