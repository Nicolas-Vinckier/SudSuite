import contextlib
import datetime
import io
import os
import tempfile
import unittest
import zipfile
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
    build_parser,
    compress_folder,
    compress_zip_python,
    decompress_archive,
    decompress_folder_archives,
    decompress_single_archive,
    extract_zip_python,
    find_archive_files,
    inspect_zip_for_extraction,
    safe_member_path,
    scan_folder,
    Toolchain,
    _split_input_paths,
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

    def test_archive_scan_applies_custom_exclusions(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "keep").mkdir()
            (root / "cache").mkdir()
            (root / "docs").mkdir()
            (root / "keep" / "photo.jpg").write_bytes(b"media")
            (root / "cache" / "temp.jpg").write_bytes(b"ignore-folder")
            (root / "docs" / "draft.md").write_bytes(b"ignore-extension")
            (root / "secret.txt").write_bytes(b"ignore-file")

            entries, total_size, skipped = scan_folder(
                root,
                quiet=True,
                exclude_folders=["cache"],
                exclude_files=["secret.txt"],
                exclude_extensions=[".md"],
            )

            self.assertEqual(
                [entry.arcname for entry in entries],
                [str(Path("keep") / "photo.jpg")],
            )
            self.assertEqual(total_size, 5)
            self.assertEqual(skipped, [])

    def test_archive_parser_accepts_repeatable_exclusions(self):
        args = build_parser().parse_args(
            [
                "--input",
                "source",
                "--exclude-folder",
                "cache,tmp",
                "--exclude-file",
                "secret.txt",
                "--exclude-ext",
                "log",
            ]
        )

        self.assertEqual(args.input, ["source"])
        self.assertEqual(args.exclude_folder, ["cache,tmp"])
        self.assertEqual(args.exclude_file, ["secret.txt"])
        self.assertEqual(args.exclude_extension, ["log"])

    def test_drag_drop_input_can_contain_multiple_quoted_folders(self):
        raw_input = '"T:\\CLIENTS\\Projet A" "T:\\CLIENTS\\Projet B"'

        self.assertEqual(
            _split_input_paths(raw_input),
            ["T:\\CLIENTS\\Projet A", "T:\\CLIENTS\\Projet B"],
        )

    def test_compress_multiple_folders_into_one_zip(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = root / "Premier dossier"
            second = root / "Second dossier"
            output = root / "archives"
            first.mkdir()
            second.mkdir()
            (first / "a.txt").write_bytes(b"A")
            (second / "b.txt").write_bytes(b"B")

            args = build_parser().parse_args(
                [
                    "--action",
                    "compress",
                    "--input",
                    str(first),
                    str(second),
                    "--mode",
                    "1",
                    "--output",
                    str(output),
                    "--engine",
                    "python",
                    "--verify",
                    "none",
                    "--quiet",
                    "--batch-archive",
                    "single",
                ]
            )
            with (
                mock.patch("SudMedia.folder_compressor.configure_console_output"),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                status = compress_folder(args)

            self.assertEqual(status, 0)
            archives = list(output.glob("Dossiers_Archive_*.zip"))
            self.assertEqual(len(archives), 1)
            with zipfile.ZipFile(archives[0]) as archive:
                self.assertEqual(
                    sorted(archive.namelist()),
                    [
                        "Premier dossier/a.txt",
                        "Second dossier/b.txt",
                    ],
                )

    def test_compress_multiple_folders_into_separate_zips(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = root / "Premier"
            second = root / "Second"
            output = root / "archives"
            first.mkdir()
            second.mkdir()
            (first / "a.txt").write_bytes(b"A")
            (second / "b.txt").write_bytes(b"B")

            args = build_parser().parse_args(
                [
                    "--action",
                    "compress",
                    "--input",
                    str(first),
                    str(second),
                    "--mode",
                    "1",
                    "--output",
                    str(output),
                    "--engine",
                    "python",
                    "--verify",
                    "none",
                    "--quiet",
                    "--batch-archive",
                    "separate",
                ]
            )
            with (
                mock.patch("SudMedia.folder_compressor.configure_console_output"),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                status = compress_folder(args)

            self.assertEqual(status, 0)
            self.assertEqual(len(list(output.glob("Premier_Archive_*.zip"))), 1)
            self.assertEqual(len(list(output.glob("Second_Archive_*.zip"))), 1)

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

    def test_python_zip_clamps_timestamps_before_1980(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            old_file = source / "old.txt"
            old_file.write_bytes(b"archive me")
            old_timestamp = datetime.datetime(1979, 1, 1).timestamp()
            os.utime(old_file, (old_timestamp, old_timestamp))
            archive = root / "archive.zip"

            entries, total_size, skipped = scan_folder(source, quiet=True)
            self.assertEqual(skipped, [])
            compress_zip_python(entries, total_size, archive, "1", quiet=True)

            with zipfile.ZipFile(archive) as compressed:
                self.assertEqual(compressed.read("old.txt"), b"archive me")
                self.assertEqual(compressed.getinfo("old.txt").date_time[:3], (1980, 1, 1))

    def test_single_folder_external_compression_runs_from_source_folder(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "NV"
            source.mkdir()
            (source / "Administratif").mkdir()
            (source / "Administratif" / "doc.txt").write_bytes(b"doc")
            output = root / "archives"
            captured = {}

            def fake_execute_compression(
                mode,
                backends,
                entries,
                total_size,
                target_folder,
                output_path,
                tools,
                requested_threads,
                quiet=False,
            ):
                captured["target_folder"] = Path(target_folder)
                Path(output_path).write_bytes(b"fake zip")
                return "7zip"

            args = build_parser().parse_args(
                [
                    "--action",
                    "compress",
                    "--input",
                    str(source),
                    "--mode",
                    "1",
                    "--output",
                    str(output),
                    "--engine",
                    "external",
                    "--verify",
                    "none",
                    "--quiet",
                ]
            )
            with (
                mock.patch("SudMedia.folder_compressor.configure_console_output"),
                mock.patch("SudMedia.folder_compressor.detect_toolchain", return_value=Toolchain(sevenzip="7z")),
                mock.patch("SudMedia.folder_compressor.execute_compression", side_effect=fake_execute_compression),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                status = compress_folder(args)

            self.assertEqual(status, 0)
            self.assertEqual(captured["target_folder"], source)

    def test_find_archive_files_detects_archives(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            sub = root / "subfolder"
            sub.mkdir()
            (root / "arch1.zip").write_bytes(b"PK")
            (root / "arch2.tar.xz").write_bytes(b"\xfd7zXZ\x00")
            (root / "not_archive.txt").write_bytes(b"text")
            (sub / "arch3.zip").write_bytes(b"PK")

            # Non récursif
            found_flat = find_archive_files(root, recursive=False)
            names_flat = [p.name for p in found_flat]
            self.assertIn("arch1.zip", names_flat)
            self.assertIn("arch2.tar.xz", names_flat)
            self.assertNotIn("arch3.zip", names_flat)
            self.assertNotIn("not_archive.txt", names_flat)

            # Récursif
            found_rec = find_archive_files(root, recursive=True)
            names_rec = [p.name for p in found_rec]
            self.assertIn("arch1.zip", names_rec)
            self.assertIn("arch2.tar.xz", names_rec)
            self.assertIn("arch3.zip", names_rec)

    def test_decompress_folder_archives_batch(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            folder_with_archives = root / "archives_in"
            folder_with_archives.mkdir()

            # Créer deux archives de test
            src1 = root / "src1"
            src1.mkdir()
            (src1 / "doc1.txt").write_bytes(b"Fichier 1")
            entries1, size1, _ = scan_folder(src1, quiet=True)
            arch1 = folder_with_archives / "8 oct. a 09-23.zip"
            compress_zip_python(entries1, size1, arch1, "1", quiet=True)

            src2 = root / "src2"
            src2.mkdir()
            (src2 / "doc2.txt").write_bytes(b"Fichier 2")
            entries2, size2, _ = scan_folder(src2, quiet=True)
            arch2 = folder_with_archives / "8 oct. a 10-57.zip"
            compress_zip_python(entries2, size2, arch2, "1", quiet=True)

            out_dir = root / "extracted_all"
            args = build_parser().parse_args([
                "--action", "decompress",
                "--input", str(folder_with_archives),
                "--output", str(out_dir),
                "--quiet",
            ])
            res = decompress_archive(args)
            self.assertEqual(res, 0)

            # Vérifier que les sous-dossiers ont été créés et contiennent les fichiers
            dest1 = out_dir / "8 oct. a 09-23"
            dest2 = out_dir / "8 oct. a 10-57"
            self.assertTrue((dest1 / "doc1.txt").is_file())
            self.assertEqual((dest1 / "doc1.txt").read_bytes(), b"Fichier 1")
            self.assertTrue((dest2 / "doc2.txt").is_file())
            self.assertEqual((dest2 / "doc2.txt").read_bytes(), b"Fichier 2")

    def test_decompress_folder_archives_flat_mode(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            folder_with_archives = root / "archives_in"
            folder_with_archives.mkdir()

            src = root / "src"
            src.mkdir()
            (src / "unique_doc.txt").write_bytes(b"Contenu direct")
            entries, size, _ = scan_folder(src, quiet=True)
            arch = folder_with_archives / "Archive_Test.zip"
            compress_zip_python(entries, size, arch, "1", quiet=True)

            out_dir = root / "extracted_flat"
            args = build_parser().parse_args([
                "--action", "decompress",
                "--input", str(folder_with_archives),
                "--output", str(out_dir),
                "--flat",
                "--quiet",
            ])
            res = decompress_archive(args)
            self.assertEqual(res, 0)
            self.assertTrue((out_dir / "unique_doc.txt").is_file())
            self.assertEqual((out_dir / "unique_doc.txt").read_bytes(), b"Contenu direct")

    def test_decompress_skips_identical_archive_rerun(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            src = root / "src"
            src.mkdir()
            (src / "fichier.txt").write_bytes(b"Donnees identiques")
            entries, size, _ = scan_folder(src, quiet=True)
            arch = root / "Archive.zip"
            compress_zip_python(entries, size, arch, "1", quiet=True)

            out_dir = root / "output"
            # Premier unzip
            args = build_parser().parse_args([
                "-d", "-i", str(arch), "-o", str(out_dir), "--quiet"
            ])
            res1 = decompress_archive(args)
            self.assertEqual(res1, 0)
            dest_file = out_dir / "Archive" / "fichier.txt"
            self.assertTrue(dest_file.is_file())
            mtime_before = dest_file.stat().st_mtime_ns

            # Second unzip (même archive)
            res2 = decompress_archive(args)
            self.assertEqual(res2, 0)
            mtime_after = dest_file.stat().st_mtime_ns
            # Vérifier que le fichier n'a pas été réécrit ni dupliqué
            self.assertEqual(mtime_before, mtime_after)
            self.assertFalse((out_dir / "Archive" / "fichier_2.txt").exists())

    def test_decompress_renames_on_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            out_dir = root / "output"
            out_dir.mkdir()
            target_folder = out_dir / "MonArchive"
            target_folder.mkdir()
            # Fichier existant avec un contenu A
            existing_file = target_folder / "rapport.txt"
            existing_file.write_bytes(b"Version A existante")

            # Nouvelle archive contenant rapport.txt avec un contenu B différent
            src = root / "src"
            src.mkdir()
            (src / "rapport.txt").write_bytes(b"Version B nouvelle")
            entries, size, _ = scan_folder(src, quiet=True)
            arch = root / "MonArchive.zip"
            compress_zip_python(entries, size, arch, "1", quiet=True)

            args = build_parser().parse_args([
                "-d", "-i", str(arch), "-o", str(out_dir), "--quiet"
            ])
            res = decompress_archive(args)
            self.assertEqual(res, 0)

            # L'ancien fichier reste intact
            self.assertEqual(existing_file.read_bytes(), b"Version A existante")
            # Le nouveau fichier a été extrait sous un nom numéroté
            renamed_file = target_folder / "rapport_2.txt"
            self.assertTrue(renamed_file.is_file())
            self.assertEqual(renamed_file.read_bytes(), b"Version B nouvelle")


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
