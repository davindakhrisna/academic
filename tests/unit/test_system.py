import subprocess
import unittest
from unittest.mock import patch

from main.errors import AcademicError
from main.system import run_command


class SystemTests(unittest.TestCase):
    def test_hyprctl_failure_reports_command_and_compositor_reply(self):
        args = ["hyprctl", "dispatch", "sendshortcut", ",mouse:272,address:0xabc"]
        for stdout, stderr in (
            (b"error: Invalid dispatcher", b""),
            (b"", b"Couldn't connect to the socket"),
        ):
            result = subprocess.CompletedProcess(args, 7, stdout, stderr)
            with (
                self.subTest(stderr=stderr),
                patch("main.system.subprocess.run", return_value=result),
                self.assertRaises(AcademicError) as caught,
            ):
                run_command(args)
            self.assertIn("hyprctl dispatch sendshortcut", str(caught.exception))
            self.assertIn((stderr or stdout).decode(), str(caught.exception))

    def test_other_command_errors_do_not_expose_arguments_or_output(self):
        args = ["notify-send", "private text"]
        result = subprocess.CompletedProcess(args, 1, b"private stdout", b"private stderr")
        with (
            patch("main.system.subprocess.run", return_value=result),
            self.assertRaises(AcademicError) as caught,
        ):
            run_command(args)
        self.assertEqual(str(caught.exception), "notify-send failed (exit 1).")
