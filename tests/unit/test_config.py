import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main.config import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    config_path,
    load_config,
    parse_env,
    set_model,
)
from main.errors import AcademicError


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="academic config ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / ".env"

    def test_quotes_exports_comments_and_single_key(self):
        self.path.write_text('export ROUTER_API_KEY="primary" # comment\nROUTER_API_KEY_BACKUP=\n')
        config = load_config({}, self.path)
        self.assertEqual(config.key, "primary")
        self.assertEqual(config.model, DEFAULT_MODEL)
        self.assertNotIn("primary", repr(config))

    def test_file_overrides_environment_and_legacy_keys_are_ignored(self):
        self.path.write_text(
            "ROUTER_API_KEY=one\nROUTER_API_KEY_BACKUP=ignored\n"
            "ROUTER_API_KEY_TERTIARY=ignored\nROUTER_MODEL=my-model\n"
            "OPENROUTER_MODEL=ignored\nOPENROUTER_FALLBACK_MODEL=ignored\n"
        )
        config = load_config({"ROUTER_API_KEY": "ignored"}, self.path)
        self.assertEqual(config.key, "one")
        self.assertEqual(config.model, "my-model")
        self.assertEqual(config.base_url, DEFAULT_BASE_URL)

    def test_environment_only_configuration(self):
        self.assertEqual(load_config({"ROUTER_API_KEY": "one"}, self.path).key, "one")

    def test_custom_gateway_url_is_normalized(self):
        config = load_config({"ROUTER_BASE_URL": "http://localhost:8080/v1/"}, self.path)
        self.assertEqual(config.base_url, "http://localhost:8080/v1")
        self.assertEqual(config.key, "")

    def test_invalid_gateway_urls_fail_without_exposing_values(self):
        for url in (
            "file:///tmp/private",
            "http://user:secret@localhost/v1",
            "http://localhost:bad/v1",
            "http://localhost:0/v1",
            "http://[invalid/v1",
            "http://localhost/v1?secret=yes",
            "http://localhost/v1#secret",
            "http://local host/v1",
            "http://localhost/v1\n",
        ):
            with self.subTest(url=url), self.assertRaises(AcademicError) as error:
                load_config({"ROUTER_BASE_URL": url}, self.path)
            self.assertNotIn("secret", str(error.exception))

    def test_default_local_gateway_does_not_require_a_key(self):
        config = load_config({"ROUTER_API_KEY_BACKUP": "old-secret"}, self.path)
        self.assertEqual(config.key, "")
        self.assertEqual(config.model, "Academic")

    def test_academic_combo_loads_and_persists(self):
        self.path.write_text("ROUTER_API_KEY=sk-or-v1-test\n")
        config = load_config({}, self.path)
        self.assertEqual(config.model, "Academic")
        self.assertEqual(config.base_url, DEFAULT_BASE_URL)
        set_model("Academic", self.path)
        self.assertEqual(load_config({}, self.path), config)

    def test_upstream_provider_keys_are_not_sent_to_gateway(self):
        config = load_config(
            {"GOOGLE_API_KEY": "google-secret", "OPENROUTER_API_KEY": "upstream-secret"},
            self.path,
        )
        self.assertEqual(config.key, "")

    def test_dotted_key_is_accepted_without_modification(self):
        self.path.write_text("ROUTER_API_KEY=sk-or-v1.key\n")
        self.assertEqual(load_config({}, self.path).key, "sk-or-v1.key")

    def test_missing_explicit_config_fails(self):
        with self.assertRaisesRegex(AcademicError, "does not exist"):
            load_config({"ACADEMIC_ENV_FILE": str(self.path), "ROUTER_API_KEY": "one"}, self.path)

    def test_invalid_config_diagnostics_do_not_expose_values(self):
        for text in (
            'ROUTER_API_KEY="secret\n',
            "secret arbitrary command",
            "KEY=unquoted words",
        ):
            with self.subTest(text=text), self.assertRaises(AcademicError) as error:
                parse_env(text)
            self.assertNotIn("secret", str(error.exception))

    def test_shell_commands_are_never_executed(self):
        self.assertEqual(
            parse_env('KEY="$(touch /tmp/never-run)"')["KEY"], "$(touch /tmp/never-run)"
        )

    def test_invalid_model_and_keys_fail(self):
        for environ in (
            {"ROUTER_API_KEY": "one", "ROUTER_MODEL": "bad//model"},
            {"ROUTER_API_KEY": "bad key"},
            {"ROUTER_API_KEY": "your_9router_api_key_here"},
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
            "# keep\nROUTER_API_KEY=secret\nexport ROUTER_MODEL=old\nROUTER_MODEL=duplicate\n"
        )
        self.path.chmod(0o600)
        set_model("new-model", self.path)
        content = self.path.read_text()
        self.assertIn("# keep", content)
        self.assertIn("ROUTER_API_KEY=secret", content)
        self.assertEqual(content.count("ROUTER_MODEL="), 1)
        self.assertEqual(load_config({}, self.path).model, "new-model")
        if os.name != "nt":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_update_failure_leaves_original_intact(self):
        self.path.write_text("ROUTER_API_KEY=secret\n")
        before = self.path.read_bytes()
        with (
            patch("main.config.os.replace", side_effect=OSError),
            self.assertRaises(AcademicError),
        ):
            set_model("new", self.path)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.root.iterdir()), [self.path])

    def test_invalid_update_leaves_original_intact(self):
        self.path.write_text('ROUTER_API_KEY="private\n')
        before = self.path.read_bytes()
        for model in ("bad//model", "valid"):
            with self.subTest(model=model), self.assertRaises(AcademicError):
                set_model(model, self.path)
            self.assertEqual(self.path.read_bytes(), before)

    def test_new_configuration_is_private(self):
        set_model("new", self.path)
        self.assertEqual(self.path.read_text(), "ROUTER_MODEL=new\n")
        if os.name != "nt":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    @unittest.skipIf(os.name == "nt", "Windows symlinks may require developer mode")
    def test_model_update_follows_symlink(self):
        target = self.root / "target"
        target.write_text("ROUTER_API_KEY=secret\n")
        self.path.symlink_to(target)
        set_model("new", self.path)
        self.assertTrue(self.path.is_symlink())
        self.assertIn("ROUTER_MODEL=new", target.read_text())
