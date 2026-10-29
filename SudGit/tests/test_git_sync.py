import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from SudGit import sud_git_sync as git_sync


@unittest.skipUnless(shutil.which("git"), "git requis")
class GitSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_branch_detection_on_local_repository(self):
        repo = self.root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--allow-empty", "-m", "i"],
            cwd=repo, check=True, capture_output=True,
        )
        self.assertEqual(git_sync.detecter_branche_depot(str(repo)), "main")
        self.assertEqual(git_sync.detecter_branche_depot(str(self.root / "absent")), "Inaccessible")

    def test_config_round_trip_is_atomic_and_has_defaults(self):
        config_file = self.root / "cfg" / "sud_git_config.json"
        with patch.object(git_sync, "CONFIG_FILE", str(config_file)):
            self.assertEqual(git_sync.charger_config()["depots"], [])
            git_sync.sauvegarder_config({"depots": [{"path": "x"}]})
            loaded = git_sync.charger_config()
        self.assertEqual(loaded["depots"], [{"path": "x"}])
        self.assertEqual(loaded["intervalle"], 60)
        self.assertEqual(json.loads(config_file.read_text(encoding="utf-8"))["depots"], [{"path": "x"}])
        self.assertEqual(list(config_file.parent.glob(".*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
