import contextlib
import datetime
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from ._path_setup import add_project_root
except ImportError:
    from _path_setup import add_project_root

add_project_root()

from SudMedia.folder_compressor import (
    ExtractionBackendError,
    archive_base_name,
    compress_zip_python,
    extract_zip_python,
    inspect_zip_for_extraction,
    safe_member_path,
    scan_folder,
)
from SudMedia.folder_weight import scan_folder as scan_folder_weights
from SudMedia.image_renamer import format_timestamp, get_unique_filename
from SudMedia import image_sorting
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

    def test_python_zip_round_trip_preserves_content(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            (source / "album").mkdir()
            expected = b"contenu de test"
            (source / "album" / "photo.txt").write_bytes(expected)
            archive = root / "archive.zip"
            destination = root / "restaure"

            entries, total_size, skipped = scan_folder(source, quiet=True)
            self.assertEqual(skipped, [])
            compress_zip_python(entries, total_size, archive, "1", quiet=True)
            file_infos, extracted_size = inspect_zip_for_extraction(
                archive, destination
            )
            extract_zip_python(
                archive,
                destination,
                file_infos,
                extracted_size,
                workers=2,
                quiet=True,
            )

            self.assertEqual(
                (destination / "album" / "photo.txt").read_bytes(),
                expected,
            )


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
    def test_sorting_config_directory_is_created_automatically(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            config_directory = Path(temporary_directory) / "configs"
            config_file = config_directory / "image_sorting_config.json"
            config = {"source": "photos", "destination": "tri"}

            with (
                mock.patch.object(
                    image_sorting, "CONFIG_DIRECTORY", config_directory
                ),
                mock.patch.object(image_sorting, "CONFIG_FILE", config_file),
            ):
                image_sorting.sauvegarder_config(config)

            self.assertTrue(config_directory.is_dir())
            self.assertEqual(
                config_file.read_text(encoding="utf-8"),
                '{\n    "source": "photos",\n    "destination": "tri"\n}',
            )

    def test_legacy_sorting_config_is_migrated(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config_directory = root / "configs"
            config_file = config_directory / "image_sorting_config.json"
            legacy_config = root / "image_sorting_config.json"
            legacy_config.write_text('{"source": "photos"}', encoding="utf-8")

            with (
                mock.patch.object(
                    image_sorting, "CONFIG_DIRECTORY", config_directory
                ),
                mock.patch.object(image_sorting, "CONFIG_FILE", config_file),
                mock.patch.object(
                    image_sorting, "LEGACY_CONFIG_FILE", legacy_config
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                loaded = image_sorting.charger_config()

            self.assertEqual(loaded, {"source": "photos"})
            self.assertTrue(config_file.exists())
            self.assertFalse(legacy_config.exists())

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
