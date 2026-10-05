import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from academia import config
from academia.system import external_environment


class FrozenTests(unittest.TestCase):
    def test_configuration_uses_executable_directory_when_frozen(self):
        original = config.ROOT
        try:
            with (
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "executable", str(original / "dist" / "academic")),
            ):
                importlib.reload(config)
                self.assertEqual(config.ROOT, (original / "dist").resolve())
                self.assertEqual(config.config_path({}, home=Path("/unused")), config.ROOT / ".env")
        finally:
            importlib.reload(config)

    def test_linux_restores_original_library_path_without_changing_parent(self):
        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "platform", "linux"),
            patch.dict(os.environ, {"LD_LIBRARY_PATH": "bundle", "LD_LIBRARY_PATH_ORIG": "system"}),
            external_environment() as environment,
        ):
            self.assertEqual(environment["LD_LIBRARY_PATH"], "system")
            self.assertEqual(os.environ["LD_LIBRARY_PATH"], "bundle")

    def test_linux_removes_bundle_path_when_original_is_missing(self):
        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "platform", "linux"),
            patch.dict(os.environ, {"LD_LIBRARY_PATH": "bundle"}, clear=True),
            external_environment() as environment,
        ):
            self.assertNotIn("LD_LIBRARY_PATH", environment)

    def test_windows_restores_dll_directory_even_on_failure(self):
        library = Mock()
        library.kernel32.SetDllDirectoryW.return_value = 1
        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "_MEIPASS", "bundle", create=True),
            patch.object(sys, "platform", "win32"),
            patch("academia.system.ctypes.windll", library, create=True),
            self.assertRaises(RuntimeError),
            external_environment(),
        ):
            raise RuntimeError("test failure")
        self.assertEqual(
            [call.args for call in library.kernel32.SetDllDirectoryW.call_args_list],
            [(None,), ("bundle",)],
        )
