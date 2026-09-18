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

try:
    from PIL import Image
except ImportError:
    Image = None

from SudMedia.sudmedia_utils import (
    Progress,
    ProcessingStats,
    analyze_quality,
    analyze_size_change,
    clean_input_path,
    collect_target_files,
    format_size,
    image_save_options,
    normalize_quality,
    paths_overlap,
    prepare_image_for_format,
    prepare_image_for_quality,
    print_processing_summary,
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

    def test_progress_supports_files_bytes_and_indeterminate_work(self):
        progress = Progress(2, 100, enabled=False)
        progress.set_item("photo.jpg", "Compression")
        progress.update_bytes(40)
        progress.complete_file(10)

        self.assertEqual(progress.completed_files, 1)
        self.assertEqual(progress.processed_bytes, 50)
        self.assertEqual(progress.current_item, "photo.jpg")

        indeterminate = Progress(None, label="Analyse", enabled=False)
        indeterminate.advance(item="fichier.bin")
        self.assertTrue(indeterminate.indeterminate)
        self.assertEqual(indeterminate.completed_files, 1)

    def test_archive_progress_reuses_the_shared_implementation(self):
        from SudMedia.folder_archive.progress import Progress as ArchiveProgress

        self.assertIs(ArchiveProgress, Progress)

    def test_size_analysis_reports_gain_and_increase(self):
        gain = analyze_size_change(1000, 750)
        increase = analyze_size_change(1000, 1250)

        self.assertEqual(gain.saved_bytes, 250)
        self.assertEqual(gain.reduction_percent, 25.0)
        self.assertEqual(increase.increased_bytes, 250)
        self.assertEqual(increase.reduction_percent, -25.0)

    def test_quality_is_normalized_and_classified(self):
        self.assertEqual(normalize_quality("150"), 100)
        self.assertEqual(normalize_quality("invalide", default=70), 70)
        self.assertEqual(analyze_quality(40).risk_level, "ÉLEVÉ")
        self.assertEqual(analyze_quality(70).risk_level, "MODÉRÉ")
        self.assertEqual(analyze_quality(90).risk_level, "FAIBLE")

    def test_processing_summary_uses_shared_statistics(self):
        stats = ProcessingStats(total_files=3)
        stats.add_success(1000, 600)
        stats.add_skipped()
        stats.add_error()
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            print_processing_summary(stats, show_duration=False)

        rendered = output.getvalue()
        self.assertIn("1/3", rendered)
        self.assertIn("Fichiers ignorés : 1", rendered)
        self.assertIn("Gain d'espace", rendered)


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

    def test_save_options_are_shared_by_format_and_mode(self):
        self.assertEqual(
            image_save_options("WEBP", compression_mode="lossless")["lossless"],
            True,
        )
        self.assertEqual(
            image_save_options("JPEG", compression_mode="lossy", quality=70)[
                "quality"
            ],
            70,
        )

    def test_lossy_png_uses_a_reduced_palette(self):
        source = Image.new("RGB", (10, 10), "red")
        prepared = prepare_image_for_quality(
            source,
            "PNG",
            compression_mode="lossy",
            quality=50,
        )
        self.assertEqual(prepared.mode, "P")

    def test_image_compressor_reuses_shared_quality_rules(self):
        from SudMedia.image_compressor import compress_image

        with tempfile.TemporaryDirectory() as temporary_directory:
            source_path = Path(temporary_directory) / "source.bmp"
            Image.effect_noise((128, 128), 100).save(source_path, "BMP")

            with contextlib.redirect_stdout(io.StringIO()):
                settings = compress_image(
                    source_path,
                    settings={
                        "choix": "2",
                        "quality": 30,
                        "use_webp": True,
                        "skip_if_larger": False,
                    },
                )

            output_path = source_path.with_name("source_min.webp")
            self.assertTrue(output_path.exists())
            self.assertEqual(settings["quality"], 30)
            with Image.open(output_path) as result:
                self.assertEqual(result.format, "WEBP")

    def test_image_master_reuses_shared_quality_and_summary(self):
        from SudMedia import image_master

        with tempfile.TemporaryDirectory() as temporary_directory:
            source_path = Path(temporary_directory) / "source.png"
            Image.effect_noise((64, 64), 100).convert("RGB").save(
                source_path, "PNG"
            )

            with (
                mock.patch.object(
                    image_master.sys,
                    "argv",
                    ["image_master.py", str(source_path)],
                ),
                mock.patch(
                    "builtins.input",
                    side_effect=["n", "n", "o", "2", "70"],
                ),
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                image_master.main()

            result_path = source_path.with_name("source_min.png")
            self.assertTrue(result_path.exists())
            self.assertIn("BILAN FINAL", output.getvalue())


if __name__ == "__main__":
    unittest.main()
