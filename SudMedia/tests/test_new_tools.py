import json
import tempfile
import unittest
from pathlib import Path

try:
    from ._path_setup import add_project_root
except ImportError:
    from _path_setup import add_project_root

add_project_root()

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import pymupdf
except ImportError:
    pymupdf = None

from SudCore.files import collect_files, hash_file
from SudMedia.duplicate import quarantine_duplicates, scan_duplicates
from SudMedia.ocr import process_documents
from SudSecurity.integrity import create_manifest, verify_manifest


class SharedFileToolsTests(unittest.TestCase):
    def test_collect_and_hash_are_reusable_across_tools(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "node_modules").mkdir()
            visible = root / "document.txt"
            visible.write_text("SudSuite", encoding="utf-8")
            (root / "node_modules" / "ignore.txt").write_text("x", encoding="utf-8")

            self.assertEqual(collect_files([root]), [visible])
            self.assertEqual(len(hash_file(visible)), 64)


class DuplicateToolTests(unittest.TestCase):
    def test_exact_duplicates_are_grouped_and_quarantined_safely(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            first = source / "original.txt"
            second = source / "copie.txt"
            unique = source / "unique.txt"
            first.write_bytes(b"identique")
            second.write_bytes(b"identique")
            unique.write_bytes(b"different")

            report = scan_duplicates([source])

            self.assertEqual(report.scanned_files, 3)
            self.assertEqual(len(report.exact_groups), 1)
            self.assertEqual(report.recoverable_bytes, len(b"identique"))

            result = quarantine_duplicates(report.exact_groups, root / "quarantaine")
            self.assertEqual(len(result.moved_files), 1)
            self.assertTrue((result.destination / "manifest.json").is_file())
            self.assertEqual(sum(path.exists() for path in (first, second)), 1)

    @unittest.skipUnless(Image, "Pillow n'est pas installé")
    def test_visually_identical_images_with_different_formats_are_found(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            image = Image.new("RGB", (40, 30), "navy")
            image.save(root / "image.png")
            image.save(root / "image.bmp")

            report = scan_duplicates([root], similar=True, similarity_threshold=0)

            self.assertEqual(len(report.exact_groups), 0)
            self.assertEqual(len(report.similar_groups), 1)


class IntegrityToolTests(unittest.TestCase):
    def test_manifest_detects_modified_missing_and_unexpected_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            root = base / "source"
            root.mkdir()
            modified = root / "modifie.txt"
            missing = root / "absent.txt"
            modified.write_text("avant", encoding="utf-8")
            missing.write_text("présent", encoding="utf-8")
            manifest = base / "integrity.json"

            create_manifest(root, manifest)
            self.assertTrue(verify_manifest(manifest, root).valid)

            modified.write_text("apres", encoding="utf-8")
            missing.unlink()
            (root / "nouveau.txt").write_text("nouveau", encoding="utf-8")
            report = verify_manifest(manifest, root)

            self.assertEqual(len(report.by_kind("modified")), 1)
            self.assertEqual(len(report.by_kind("missing")), 1)
            self.assertEqual(len(report.by_kind("unexpected")), 1)

    def test_manifest_rejects_parent_directory_escape(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = root / "bad.json"
            manifest.write_text(
                json.dumps(
                    {
                        "format": "sudsuite-integrity-v1",
                        "algorithm": "sha256",
                        "files": [
                            {
                                "path": "../secret.txt",
                                "size": 0,
                                "modified_ns": 0,
                                "sha256": "0" * 64,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                verify_manifest(manifest, root)


class FakeOCRBackend:
    def recognize(self, image_path, language="fra+eng"):
        return f"Texte reconnu en {language}"


class OCRToolTests(unittest.TestCase):
    def test_image_ocr_backend_and_text_output_are_decoupled(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            image = root / "scan.png"
            image.write_bytes(b"contenu simule")
            output = root / "sortie"

            result = process_documents(
                [image], output, FakeOCRBackend(), language="fra"
            )

            self.assertEqual(result.errors, [])
            self.assertEqual(len(result.documents), 1)
            rendered = result.outputs[0].read_text(encoding="utf-8")
            self.assertIn("Texte reconnu en fra", rendered)
            self.assertIn("Page 1", rendered)

    @unittest.skipUnless(pymupdf, "PyMuPDF n'est pas installé")
    def test_native_pdf_text_does_not_require_tesseract(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            pdf_path = root / "document.pdf"
            document = pymupdf.open()
            page = document.new_page()
            page.insert_text((72, 72), "Texte PDF natif suffisamment long pour Sud OCR")
            document.save(pdf_path)
            document.close()

            result = process_documents([pdf_path], root / "sortie", None)

            self.assertEqual(result.errors, [])
            self.assertIn("Texte PDF natif", result.documents[0].text)
            self.assertEqual(result.documents[0].pages[0].source, "texte PDF")


if __name__ == "__main__":
    unittest.main()
