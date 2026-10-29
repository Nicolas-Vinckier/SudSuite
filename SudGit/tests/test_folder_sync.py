import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from SudGit import sud_folder_sync as sync


class DeletionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.left = base / "left"
        self.right = base / "right"
        self.left.mkdir()
        self.right.mkdir()
        self.state = base / "state"
        state_patch = patch.object(sync, "STATE_DIR", self.state)
        state_patch.start()
        self.addCleanup(state_patch.stop)

    def seed(self, names):
        for root in (self.left, self.right):
            for name in names:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name, encoding="utf-8")
        sync.save_state(
            self.left,
            self.right,
            sync.scan_folder(self.left, set()),
            sync.scan_folder(self.right, set()),
        )

    def run_sync(self):
        return sync.sync_once(
            self.left, self.right, set(), propagate_deletes=True, verbose=False
        )

    def test_deletion_has_manifest_and_recoverable_file(self):
        self.seed(["keep.txt", "nested/remove.md"])
        (self.right / "nested/remove.md").unlink()
        stats = self.run_sync()
        self.assertEqual(stats.deleted_left, 1)
        self.assertFalse((self.left / "nested/remove.md").exists())
        manifest = next((self.state / "deletion_plans").rglob("*.txt"))
        self.assertIn("left | nested", manifest.read_text(encoding="utf-8"))
        self.assertEqual(
            next((self.state / "trash").rglob("remove.md")).read_text(encoding="utf-8"),
            "nested/remove.md",
        )

    def test_total_disappearance_blocks_without_changing_state(self):
        self.seed(["a.txt", "b.txt"])
        (self.right / "a.txt").unlink()
        (self.right / "b.txt").unlink()
        state_before = sync.state_file_for(self.left, self.right).read_bytes()
        with self.assertRaisesRegex(RuntimeError, "Suppression totale bloquée"):
            self.run_sync()
        self.assertTrue((self.left / "a.txt").exists())
        self.assertEqual(sync.state_file_for(self.left, self.right).read_bytes(), state_before)
        manifest = next((self.state / "deletion_plans").rglob("*.txt"))
        self.assertIn("left | a.txt", manifest.read_text(encoding="utf-8"))

    def test_dry_run_keeps_files(self):
        self.seed(["keep.txt", "remove.txt"])
        (self.right / "remove.txt").unlink()
        stats = sync.sync_once(
            self.left, self.right, set(), dry_run=True,
            propagate_deletes=True, verbose=False,
        )
        self.assertEqual(stats.deleted_left, 1)
        self.assertTrue((self.left / "remove.txt").exists())
        self.assertFalse((self.state / "trash").exists())

    def test_manifest_exists_before_first_move(self):
        self.seed(["keep.txt", "remove.txt"])
        (self.right / "remove.txt").unlink()
        actual_archive = sync.archive_file

        def check_then_archive(*args):
            self.assertEqual(len(list((self.state / "deletion_plans").rglob("*.txt"))), 1)
            return actual_archive(*args)

        with patch.object(sync, "archive_file", side_effect=check_then_archive):
            self.run_sync()


