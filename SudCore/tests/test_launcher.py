import contextlib
import io
import unittest
from unittest import mock

import sudsuite
from SudCore import Entry, launch
from SudCore import launcher as core_launcher
from SudGit import launcher as git_launcher
from SudMedia import launcher as media_launcher
from SudSecurity import launcher as security_launcher


def run(argv):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = launch("Test", TOOLS, argv)
    return code, output.getvalue()


TOOLS = (
    Entry("alpha", "Alpha", "premier", action=lambda argv: 7 if list(argv) == ["x"] else 3),
    Entry("beta", "Beta", "second", module="paquet.inexistant"),
)


class LauncherTests(unittest.TestCase):
    def test_direct_launch_by_key_and_number_passes_arguments(self):
        self.assertEqual(run(["alpha", "x"])[0], 7)
        self.assertEqual(run(["1"])[0], 3)

    def test_unknown_tool_is_rejected(self):
        code, output = run(["zzz"])
        self.assertEqual(code, 2)
        self.assertIn("Outil inconnu", output)

    def test_list_does_not_launch_anything(self):
        code, output = run(["--list"])
        self.assertEqual(code, 0)
        self.assertIn("alpha", output)

    def test_interactive_menu_runs_a_choice_then_quits(self):
        with mock.patch("builtins.input", side_effect=["1", "0"]):
            code, output = run([])
        self.assertEqual(code, 0)
        self.assertIn("À bientôt", output)

    def test_module_exit_code_is_returned(self):
        with mock.patch.object(core_launcher.runpy, "run_module", side_effect=SystemExit(4)):
            self.assertEqual(core_launcher.run_module("x"), 4)


class AskPathTests(unittest.TestCase):
    def test_zero_and_empty_cancel_and_quotes_are_removed(self):
        from SudCore import ask_path

        with mock.patch("builtins.input", side_effect=["0", "", ' "C:/a b" ']):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertIsNone(ask_path("x"))
                self.assertIsNone(ask_path("x"))
                self.assertEqual(ask_path("x"), "C:/a b")


class CatalogTests(unittest.TestCase):
    def test_every_catalog_module_exists_and_is_runnable(self):
        import importlib.util

        for package in (media_launcher, git_launcher, security_launcher):
            keys = [entry.key for entry in package.TOOLS]
            self.assertEqual(len(keys), len(set(keys)))
            for entry in package.TOOLS:
                spec = importlib.util.find_spec(entry.module)
                self.assertIsNotNone(spec, entry.module)
                self.assertIn("__name__ == \"__main__\"", open(spec.origin, encoding="utf-8").read(), entry.module)

    def test_suite_routes_to_each_package(self):
        keys = {entry.key for entry in sudsuite.PACKAGES}
        self.assertEqual(keys, {"media", "git", "security"})
        code, output = run_suite(["security", "--list"])
        self.assertEqual(code, 0)
        self.assertIn("vault", output)


def run_suite(argv):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = sudsuite.main(argv)
    return code, output.getvalue()


if __name__ == "__main__":
    unittest.main()
