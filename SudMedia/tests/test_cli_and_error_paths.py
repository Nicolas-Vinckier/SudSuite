"""Tests des interfaces CLI et des parcours d'erreur sans outils externes."""

from __future__ import annotations

import contextlib
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

from SudMedia import sud_duplicate, sud_ocr
from SudMedia.utils.filesystem.paths import (
    ExtractionBackendError,
    detect_archive_format,
    safe_member_path,
)
from SudMedia.utils.ocr import process_documents
from SudMedia.utils.ocr.models import OCRResult


class DuplicateCliTests(unittest.TestCase):
    def test_parser_accepts_similarity_options(self):
        args = sud_duplicate.build_parser().parse_args(
            ["photos", "--similar", "--threshold", "8", "--yes"]
        )

        self.assertEqual(args.paths, ["photos"])
        self.assertTrue(args.similar)
        self.assertEqual(args.threshold, 8)
        self.assertTrue(args.yes)

    def test_parser_rejects_threshold_outside_allowed_range(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                sud_duplicate.build_parser().parse_args(["--threshold", "17"])

    def test_main_rejects_missing_input_path(self):
        with (
            mock.patch.object(sud_duplicate, "configure_console_output"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            status = sud_duplicate.main(["chemin-inexistant"])

        self.assertEqual(status, 2)


class OCRCliTests(unittest.TestCase):
    def test_parser_exposes_documented_defaults(self):
        args = sud_ocr.build_parser().parse_args([])

        self.assertEqual(args.language, "fra+eng")
        self.assertEqual(args.dpi, 300)
        self.assertIsNone(args.output)

    def test_main_rejects_an_explicit_missing_tesseract_binary(self):
        with (
            mock.patch.object(sud_ocr, "configure_console_output"),
            mock.patch.object(sud_ocr, "find_tesseract", return_value=None),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            status = sud_ocr.main(["--tesseract", "inexistant.exe", "document.pdf"])

        self.assertEqual(status, 2)

    def test_main_clamps_the_requested_dpi(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            image = Path(temporary_directory) / "scan.png"
            image.write_bytes(b"image")
            with (
                mock.patch.object(sud_ocr, "configure_console_output"),
                mock.patch.object(sud_ocr, "find_tesseract", return_value=None),
                mock.patch.object(sud_ocr, "process_documents", return_value=OCRResult()) as process,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                status = sud_ocr.main(["--dpi", "1", str(image)])

        self.assertEqual(status, 1)
        self.assertEqual(process.call_args.kwargs["dpi"], 72)


class ErrorPathTests(unittest.TestCase):
    def test_image_without_backend_is_reported_without_stopping_batch(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            image = Path(temporary_directory) / "scan.jpg"
            image.write_bytes(b"image")

            result = process_documents([image], Path(temporary_directory) / "out", None)

        self.assertEqual(result.documents, [])
        self.assertEqual(result.outputs, [])
        self.assertEqual(len(result.errors), 1)
        self.assertIn("moteur OCR est requis", result.errors[0])

    def test_archive_format_and_absolute_member_are_validated(self):
        self.assertEqual(detect_archive_format("backup.txz"), "tar.xz")
        with self.assertRaises(ExtractionBackendError):
            safe_member_path("destination", "C:/Windows/system.ini")


if __name__ == "__main__":
    unittest.main()
