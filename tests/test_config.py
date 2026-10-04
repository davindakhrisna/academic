import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main.config import DEFAULT_MODEL, config_path, load_config, parse_env, set_model
from main.errors import AcademicError


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="academic config ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / ".env"

    def test_quotes_exports_comments_and_empty_backup_keys(self):
        self.path.write_text('export GOOGLE_API_KEY="primary" # comment\nGOOGLE_API_KEY_BACKUP=\n')
        config = load_config({}, self.path)
        self.assertEqual(config.keys, ("primary",))
        self.assertEqual(config.model, DEFAULT_MODEL)
        self.assertNotIn("primary", repr(config))

    def test_three_keys_and_file_overrides_environment(self):
        self.path.write_text(
            "GOOGLE_API_KEY=one\nGOOGLE_API_KEY_BACKUP=two\nGOOGLE_API_KEY_TERTIARY=three\nGEMINI_MODEL=my-model\n"
        )
        config = load_config({"GOOGLE_API_KEY": "ignored"}, self.path)
        self.assertEqual(config.keys, ("one", "two", "three"))
        self.assertEqual(config.model, "my-model")

    def test_environment_only_configuration(self):
        self.assertEqual(load_config({"GOOGLE_API_KEY": "one"}, self.path).keys, ("one",))

    def test_dotted_keys_are_accepted_without_modification(self):
        keys = ("AQ.primary_key", "AQ.backup-key", "AQ.tertiary_key")
        self.path.write_text(
            f"GOOGLE_API_KEY={keys[0]}\nGOOGLE_API_KEY_BACKUP={keys[1]}\n"
            f"GOOGLE_API_KEY_TERTIARY={keys[2]}\n"
        )
        self.assertEqual(load_config({}, self.path).keys, keys)

    def test_missing_explicit_config_fails(self):
        with self.assertRaisesRegex(AcademicError, "does not exist"):
            load_config({"ACADEMIC_ENV_FILE": str(self.path), "GOOGLE_API_KEY": "one"}, self.path)

    def test_invalid_config_diagnostics_do_not_expose_values(self):
        for text in ('GOOGLE_API_KEY="secret\n', "secret arbitrary command", "KEY=unquoted words"):
            with self.subTest(text=text), self.assertRaises(AcademicError) as error:
                parse_env(text)
            self.assertNotIn("secret", str(error.exception))

    def test_shell_commands_are_never_executed(self):
        self.assertEqual(
            parse_env('KEY="$(touch /tmp/never-run)"')["KEY"], "$(touch /tmp/never-run)"
        )

    def test_invalid_model_and_keys_fail(self):
        for environ in (
            {"GOOGLE_API_KEY": "one", "GEMINI_MODEL": "bad/model"},
            {"GOOGLE_API_KEY": "bad key"},
            {"GOOGLE_API_KEY": "your_google_api_key_here"},
            {},
        ):
            with self.subTest(environ=environ), self.assertRaises(AcademicError):
                load_config(environ, self.path)

    def test_config_precedence_and_fallback(self):
        fallback = self.root / "home" / "nixos-config" / ".env"
        fallback.parent.mkdir(parents=True)
        fallback.touch()
        self.assertEqual(config_path({}, self.root, self.root / "home"), fallback)
        self.path.touch()
        self.assertEqual(config_path({}, self.root, self.root / "home"), self.path)
        self.assertEqual(config_path({"ACADEMIC_ENV_FILE": str(fallback)}), fallback)
        self.assertEqual(config_path({"SHELLCUT_ENV_FILE": str(fallback)}), fallback)

    def test_update_preserves_keys_comments_and_permissions(self):
        self.path.write_text(
            "# keep\nGOOGLE_API_KEY=secret\nexport GEMINI_MODEL=old\nGEMINI_MODEL=duplicate\n"
        )
        self.path.chmod(0o600)
        set_model("new-model", self.path)
        content = self.path.read_text()
        self.assertIn("# keep", content)
        self.assertIn("GOOGLE_API_KEY=secret", content)
        self.assertEqual(content.count("GEMINI_MODEL="), 1)
        self.assertEqual(load_config({}, self.path).model, "new-model")
        if os.name != "nt":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_update_failure_leaves_original_intact(self):
        self.path.write_text("GOOGLE_API_KEY=secret\n")
        before = self.path.read_bytes()
        with (
            patch("main.config.os.replace", side_effect=OSError),
            self.assertRaises(AcademicError),
        ):
            set_model("new", self.path)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.root.iterdir()), [self.path])

    def test_invalid_update_leaves_original_intact(self):
        self.path.write_text('GOOGLE_API_KEY="private\n')
        before = self.path.read_bytes()
        for model in ("bad/model", "valid"):
            with self.subTest(model=model), self.assertRaises(AcademicError):
                set_model(model, self.path)
            self.assertEqual(self.path.read_bytes(), before)

    def test_new_configuration_is_private(self):
        set_model("new", self.path)
        self.assertEqual(self.path.read_text(), "GEMINI_MODEL=new\n")
        if os.name != "nt":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    @unittest.skipIf(os.name == "nt", "Windows symlinks may require developer mode")
    def test_model_update_follows_symlink(self):
        target = self.root / "target"
        target.write_text("GOOGLE_API_KEY=secret\n")
        self.path.symlink_to(target)
        set_model("new", self.path)
        self.assertTrue(self.path.is_symlink())
        self.assertIn("GEMINI_MODEL=new", target.read_text())
