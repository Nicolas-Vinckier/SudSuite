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

from SudMedia import excel_to_pdf, sud_duplicate, sud_ocr
from SudMedia.utils.office import (
    OfficeConversionError,
    SpreadsheetPdfResult,
    convert_spreadsheet_to_pdf,
)
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


class ExcelToPdfTests(unittest.TestCase):
    def test_parser_exposes_one_page_pdf_options(self):
        args = excel_to_pdf.build_parser().parse_args([])

        self.assertIsNone(args.output)
        self.assertIsNone(args.soffice)
        self.assertEqual(args.backend, "auto")
        self.assertEqual(args.timeout, 300)

    def test_conversion_uses_single_page_sheets_filter(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "rapport.xlsx"
            source.write_bytes(b"tableur")
            output = root / "pdf"

            def fake_run(command, **_kwargs):
                export_dir = Path(command[command.index("--outdir") + 1])
                (export_dir / "rapport.pdf").write_bytes(b"pdf")
                return mock.Mock(returncode=0, stdout="", stderr="")

            with (
                mock.patch(
                    "SudMedia.utils.office.spreadsheet_pdf.find_soffice",
                    return_value="soffice",
                ),
                mock.patch(
                    "SudMedia.utils.office.spreadsheet_pdf.subprocess.run",
                    side_effect=fake_run,
                ) as run,
            ):
                result = convert_spreadsheet_to_pdf(source, output, backend="libreoffice")

            command = run.call_args.args[0]
            self.assertIn("SinglePageSheets", command[command.index("--convert-to") + 1])
            self.assertTrue(any(argument.startswith("-env:UserInstallation=") for argument in command))
            self.assertEqual(result.output, output / "rapport.pdf")
            self.assertEqual(result.output.read_bytes(), b"pdf")

    def test_excel_backend_fits_each_sheet_on_one_page(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "rapport.xlsx"
            source.write_bytes(b"tableur")
            output = root / "pdf"

            def fake_run(command, **_kwargs):
                script = command[-1]
                output_path = script.split("ExportAsFixedFormat(0, '", 1)[1].split("'", 1)[0]
                Path(output_path).write_bytes(b"pdf")
                return mock.Mock(returncode=0, stdout="", stderr="")

            with (
                mock.patch(
                    "SudMedia.utils.office.spreadsheet_pdf.find_excel",
                    return_value="powershell.exe",
                ),
                mock.patch(
                    "SudMedia.utils.office.spreadsheet_pdf.subprocess.run",
                    side_effect=fake_run,
                ) as run,
            ):
                result = convert_spreadsheet_to_pdf(source, output, backend="excel")

            script = run.call_args.args[0][-1]
            self.assertIn("FitToPagesWide = 1", script)
            self.assertIn("FitToPagesTall = 1", script)
            self.assertEqual(result.output.read_bytes(), b"pdf")

    def test_main_continues_when_one_conversion_fails(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = root / "premier.xlsx"
            second = root / "second.xlsx"
            first.write_bytes(b"one")
            second.write_bytes(b"two")
            output = root / "pdf"

            with (
                mock.patch.object(excel_to_pdf, "configure_console_output"),
                mock.patch.object(
                    excel_to_pdf,
                    "convert_spreadsheet_to_pdf",
                    side_effect=[
                        SpreadsheetPdfResult(first, output / "premier.pdf"),
                        OfficeConversionError("conversion impossible"),
                    ],
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                status = excel_to_pdf.main([str(first), str(second), "-o", str(output)])

        self.assertEqual(status, 1)


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
