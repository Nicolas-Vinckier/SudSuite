import contextlib
import datetime
import io
import tempfile
import unittest
from pathlib import Path

from SudMedia.folder_compressor import (
    ExtractionBackendError,
    archive_base_name,
    safe_member_path,
    scan_folder,
)
from SudMedia.folder_weight import scan_folder as scan_folder_weights
from SudMedia.image_renamer import format_timestamp, get_unique_filename
from SudMedia.image_sorting import get_date_from_file, valider_dossiers


class ArchiveToolTests(unittest.TestCase):
    def test_archive_name_removes_generated_suffix(self):
        self.assertEqual(
            archive_base_name("Photos_Archive_20260917_120000.tar.xz"),
            "Photos",
        )

    def test_archive_member_cannot_escape_destination(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(ExtractionBackendError):
                safe_member_path(temporary_directory, "../fichier.txt")

    def test_archive_scan_ignores_technical_directories(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / ".git").mkdir()
            (root / ".git" / "index").write_bytes(b"ignore")
            (root / "photo.jpg").write_bytes(b"media")

            entries, total_size, skipped = scan_folder(root, quiet=True)

            self.assertEqual([entry.arcname for entry in entries], ["photo.jpg"])
            self.assertEqual(total_size, 5)
            self.assertEqual(skipped, [])


class FolderWeightToolTests(unittest.TestCase):
    def test_weight_scan_aggregates_children(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            child = root / "album"
            child.mkdir()
            (child / "photo.jpg").write_bytes(b"123456")
            stats = {"folders_scanned": 0, "files_scanned": 0}

            node = scan_folder_weights(
                folder_path=root,
                root_path=root,
                excluded_names=set(),
                top_files_heap=[],
                top_files_limit=None,
                errors=[],
                stats=stats,
            )

            self.assertEqual(node.size, 6)
            self.assertEqual(node.file_count, 1)
            self.assertEqual(node.dir_count, 1)


class MediaOrganizationToolTests(unittest.TestCase):
    def test_filename_date_detection(self):
        year, month = get_date_from_file(
            "IMG_20260917.jpg",
            "IMG_20260917.jpg",
            "nom",
            "AAAAMMDD",
        )
        self.assertEqual((year, month), ("2026", "Septembre"))

    def test_sorting_rejects_nested_source_and_destination(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            nested = root / "destination"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertFalse(
                    valider_dossiers(
                        {"source": str(root), "destination": str(nested)}
                    )
                )

    def test_renamer_tokens_and_collision_index(self):
        timestamp = datetime.datetime(2026, 9, 17, 12, 34, 56).timestamp()
        self.assertEqual(
            format_timestamp(timestamp, "YYYY-MM-DD_HHmmSS"),
            "2026-09-17_123456",
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "photo_1.jpg").touch()
            name = get_unique_filename(root, "photo_#", ".jpg")
            self.assertEqual(name, "photo_2")


if __name__ == "__main__":
    unittest.main()
