import contextlib
import io
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

from SudMedia.sudmedia_utils import (
    clean_input_path,
    collect_target_files,
    format_size,
    paths_overlap,
    prepare_image_for_format,
    render_progress,
    reserve_output_path,
    resize_image,
    unique_available_path,
)


class PathUtilitiesTests(unittest.TestCase):
    def test_clean_input_path_only_removes_matching_outer_quotes(self):
        self.assertEqual(clean_input_path('  "C:/Mes images"  '), "C:/Mes images")
        self.assertEqual(clean_input_path("photo's.jpg"), "photo's.jpg")
        self.assertEqual(clean_input_path(None), "")

    def test_collect_target_files_is_recursive_filtered_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            visible = root / "album"
            ignored = root / "node_modules"
            hidden = root / ".cache"
            visible.mkdir()
            ignored.mkdir()
            hidden.mkdir()
            first = root / "photo.JPG"
            second = visible / "vacances.png"
            first.write_bytes(b"jpg")
            second.write_bytes(b"png")
            (ignored / "ignore.jpg").write_bytes(b"jpg")
            (hidden / "ignore.png").write_bytes(b"png")

            files = collect_target_files(
                [f'"{root}"', str(first)],
                ("jpg", ".png"),
                reporter=None,
            )

            self.assertEqual(files, [str(first), str(second)])

    def test_reserve_output_path_suffixes_only_batch_collisions(self):
        reserved = set()
        first = reserve_output_path("sortie/photo.jpg", reserved)
        second = reserve_output_path("sortie/photo.jpg", reserved)
        third = reserve_output_path("sortie/photo.jpg", reserved)

        self.assertEqual(Path(first).name, "photo.jpg")
        self.assertEqual(Path(second).name, "photo_2.jpg")
        self.assertEqual(Path(third).name, "photo_3.jpg")

    def test_paths_overlap_detects_nested_directories(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            child = root / "destination"
            sibling = root.parent / f"{root.name}_sibling"

            self.assertTrue(paths_overlap(root, child))
            self.assertFalse(paths_overlap(root, sibling))

    def test_unique_available_path_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            original = Path(temporary_directory) / "photo.jpg"
            second = Path(temporary_directory) / "photo_2.jpg"
            original.touch()
            second.touch()

            available = unique_available_path(original)

            self.assertEqual(Path(available).name, "photo_3.jpg")


class DisplayUtilitiesTests(unittest.TestCase):
    def test_format_size_uses_expected_units(self):
        self.assertEqual(format_size(0), "0.00 O")
        self.assertEqual(format_size(1024), "1.00 Ko")
        self.assertEqual(format_size(1024**4), "1.00 To")

    def test_progress_accepts_empty_totals(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            render_progress(0, 0, "image.png", total_steps=0)
        self.assertIn("image.png", output.getvalue())


@unittest.skipUnless(Image, "Pillow n'est pas installé")
class ImageUtilitiesTests(unittest.TestCase):
    def test_resize_modes_have_the_requested_dimensions(self):
        source = Image.new("RGB", (400, 200), "red")

        self.assertEqual(resize_image(source.copy(), 100, None).size, (100, 50))
        self.assertEqual(resize_image(source.copy(), 100, 100, "1").size, (100, 100))
        self.assertEqual(resize_image(source.copy(), 100, 100, "2").size, (100, 100))
        self.assertEqual(resize_image(source.copy(), 100, 100, "3").size, (100, 100))

    def test_jpeg_transparency_is_flattened_on_white(self):
        transparent = Image.new("RGBA", (2, 2), (255, 0, 0, 0))
        jpeg_ready = prepare_image_for_format(transparent, "JPEG")

        self.assertEqual(jpeg_ready.mode, "RGB")
        self.assertEqual(jpeg_ready.getpixel((0, 0)), (255, 255, 255))


if __name__ == "__main__":
    unittest.main()
