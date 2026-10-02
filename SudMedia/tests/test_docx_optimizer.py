"""Tests de Sud DOCX Optimizer."""

from __future__ import annotations

import io
import random
import tempfile
import unittest
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

try:
    from ._path_setup import add_project_root
except ImportError:
    from _path_setup import add_project_root

add_project_root()

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

from SudMedia.utils.office import (
    DocxOptimizationError,
    optimize_docx,
    verify_docx_package,
)

REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"


def _image_bytes(mode: str, size: tuple[int, int], *, transparent: bool = False) -> bytes:
    rng = random.Random(12345)
    if mode == "PNG":
        if transparent:
            image = Image.new("RGBA", size, (20, 80, 180, 120))
        else:
            raw = rng.randbytes(size[0] * size[1] * 3)
            image = Image.frombytes("RGB", size, raw)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    raw = rng.randbytes(size[0] * size[1] * 3)
    image = Image.frombytes("RGB", size, raw)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=100, subsampling=0)
    return buffer.getvalue()


def _create_docx(
    path: Path,
    *,
    include_photo: bool = True,
    include_transparent: bool = False,
    include_jpeg: bool = False,
    broken_relation: bool = False,
) -> None:
    content_types = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="{CT_NS}">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Default Extension="jpeg" ContentType="image/jpeg"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''.encode("utf-8")

    package_rels = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{REL_NS}">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''.encode("utf-8")

    targets = []
    if include_photo:
        targets.append(("rId1", "media/photo.png"))
    if include_transparent:
        targets.append(("rId2", "media/transparent.png"))
    if include_jpeg:
        targets.append(("rId3", "media/existing.jpeg"))
    if broken_relation:
        targets.append(("rId9", "media/missing.png"))
    rel_lines = "\n".join(
        f'  <Relationship Id="{rel_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{target}"/>'
        for rel_id, target in targets
    )
    document_rels = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{REL_NS}">
{rel_lines}
</Relationships>'''.encode("utf-8")

    document_xml = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>'''

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", package_rels)
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/_rels/document.xml.rels", document_rels)
        if include_photo:
            archive.writestr("word/media/photo.png", _image_bytes("PNG", (320, 240)))
        if include_transparent:
            archive.writestr(
                "word/media/transparent.png",
                _image_bytes("PNG", (120, 100), transparent=True),
            )
        if include_jpeg:
            archive.writestr("word/media/existing.jpeg", _image_bytes("JPEG", (320, 240)))


@unittest.skipUnless(Image, "Pillow n'est pas installé")
class DocxOptimizerTests(unittest.TestCase):
    def test_smart_converts_opaque_photo_and_updates_ooxml_references(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.docx"
            output = root / "optimized.docx"
            _create_docx(source, include_photo=True, include_transparent=True)

            result = optimize_docx(
                source,
                output,
                mode="smart",
                jpeg_quality=82,
                min_savings_percent=5,
            )

            self.assertEqual(result.png_to_jpeg, 1)
            self.assertTrue(output.is_file())
            self.assertTrue(source.is_file())
            verify_docx_package(output)

            with zipfile.ZipFile(source) as original:
                self.assertIn("word/media/photo.png", original.namelist())
            with zipfile.ZipFile(output) as optimized:
                names = set(optimized.namelist())
                self.assertIn("word/media/photo.jpg", names)
                self.assertNotIn("word/media/photo.png", names)
                self.assertIn("word/media/transparent.png", names)

                rels = ET.fromstring(optimized.read("word/_rels/document.xml.rels"))
                targets = {
                    rel.get("Target")
                    for rel in rels.findall(f"{{{REL_NS}}}Relationship")
                }
                self.assertIn("media/photo.jpg", targets)
                self.assertIn("media/transparent.png", targets)

                content_types = ET.fromstring(optimized.read("[Content_Types].xml"))
                defaults = {
                    (item.get("Extension"), item.get("ContentType"))
                    for item in content_types.findall(f"{{{CT_NS}}}Default")
                }
                self.assertIn(("jpg", "image/jpeg"), defaults)

    def test_lossless_mode_never_changes_png_extension(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.docx"
            output = root / "optimized.docx"
            _create_docx(source, include_photo=True)

            result = optimize_docx(source, output, mode="lossless")

            self.assertEqual(result.png_to_jpeg, 0)
            with zipfile.ZipFile(output) as optimized:
                self.assertIn("word/media/photo.png", optimized.namelist())
                self.assertNotIn("word/media/photo.jpg", optimized.namelist())

    def test_aggressive_mode_can_recompress_existing_jpeg(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.docx"
            output = root / "optimized.docx"
            _create_docx(source, include_photo=False, include_jpeg=True)

            result = optimize_docx(
                source,
                output,
                mode="aggressive",
                jpeg_quality=60,
                min_savings_percent=1,
            )

            self.assertEqual(result.jpeg_recompressed, 1)
            self.assertLess(result.optimized_size, result.original_size)
            verify_docx_package(output)

    def test_original_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source.docx"
            _create_docx(source)
            with self.assertRaises(DocxOptimizationError):
                optimize_docx(source, source)

    def test_verification_detects_broken_internal_relationship(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "broken.docx"
            _create_docx(source, include_photo=False, broken_relation=True)
            with self.assertRaises(DocxOptimizationError):
                verify_docx_package(source)


if __name__ == "__main__":
    unittest.main()
