import contextlib
import io
import signal
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from academia.cli import main
from academia.config import Config
from academia.control import RunControl
from academia.errors import AcademicError, Cancelled
from tests.support.helpers import QuizDesktop, QuizVision, png


class CliTests(unittest.TestCase):
    def call(self, argv):
        self.output, self.errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(self.output), contextlib.redirect_stderr(self.errors):
            return main(argv)

    def test_help_does_not_load_configuration_or_capture(self):
        with (
            patch("academia.cli.load_config") as config,
            self.assertRaises(SystemExit) as exit_status,
        ):
            self.call(["--help"])
        self.assertEqual(exit_status.exception.code, 0)
        config.assert_not_called()

    def test_notification_clear_and_simulate_routing(self):
        for argv, function in (
            (["--notify", "Hello"], "notify"),
            (["--clear"], "clear"),
            (["--simulate"], "simulate"),
        ):
            with (
                self.subTest(argv=argv),
                patch(f"academia.cli.notifications.{function}") as operation,
                patch("academia.cli.load_config") as config,
            ):
                self.assertEqual(self.call(argv), 0)
                operation.assert_called_once()
                config.assert_not_called()

    def test_invalid_routes_return_usage_error(self):
        for argv in (
            ["--questions", "2"],
            ["--dry-run"],
            ["--run", "--questions", "0"],
            ["--run", "--questions", "abc"],
            ["--run", "--clear"],
            ["--notify"],
            ["--unknown"],
        ):
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as status:
                self.call(argv)
            self.assertEqual(status.exception.code, 2)

    def test_normal_solver_captures_and_notifies(self):
        with (
            patch("academia.cli.load_config", return_value=Config("model", "one")),
            patch("academia.cli.require_commands"),
            patch("academia.cli.capture_png", return_value=png()) as capture,
            patch("academia.cli.OpenRouterClient") as client,
            patch("academia.cli.notifications.notify") as notify,
        ):
            client.return_value.generate.return_value = "A"
            self.assertEqual(self.call([]), 0)
        capture.assert_called_once()
        notify.assert_called_once_with("A")

    def test_model_update_routing(self):
        with patch("academia.cli.set_model", return_value=Path("settings.env")) as save:
            self.assertEqual(self.call(["--set-model", "new-model"]), 0)
        save.assert_called_once_with("new-model")

    def test_runner_prompt_countdown_selects_and_stops_at_limit(self):
        desktop = QuizDesktop()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("academia.cli.load_config", return_value=Config("model", "one")),
            patch("academia.cli.require_commands"),
            patch("academia.cli.create_desktop", return_value=desktop),
            patch("academia.cli.Vision", return_value=QuizVision(desktop)),
            patch("academia.cli.RunControl", side_effect=lambda: RunControl(Path(directory))),
            patch("builtins.input", return_value="1"),
        ):
            # Constructor defaults bind at definition time; inject an immediate clock.
            from academia.runner import QuestionRunner

            with patch(
                "academia.cli.QuestionRunner",
                side_effect=lambda *a, **kw: QuestionRunner(*a, **kw, sleep=lambda _: None),
            ):
                self.assertEqual(self.call(["--run"]), 0)
        self.assertEqual(desktop.clicks, [(100, 200)])
        self.assertIn("1/1", self.output.getvalue())

    def test_errors_and_cancellation_return_nonzero(self):
        for error, expected in (
            (AcademicError("quota"), 1),
            (Cancelled(), 130),
            (KeyboardInterrupt(), 130),
        ):
            with (
                self.subTest(error=error),
                patch("academia.cli.load_config", side_effect=error),
                patch("academia.cli.notifications.report_error"),
            ):
                self.assertEqual(self.call([]), expected)

    def test_sigterm_handler_is_restored(self):
        previous = signal.getsignal(signal.SIGTERM)
        with patch("academia.cli.notifications.notify"):
            self.assertEqual(self.call(["--notify", "Hi"]), 0)
        self.assertEqual(signal.getsignal(signal.SIGTERM), previous)

    def test_stop_command_does_not_load_keys(self):
        with (
            patch("academia.cli.request_stop") as stop,
            patch("academia.cli.load_config") as config,
        ):
            self.assertEqual(self.call(["--stop"]), 0)
        stop.assert_called_once()
        config.assert_not_called()

    def test_bad_prompt_and_eof_fail_without_capture(self):
        for answer in ("zero", "0", EOFError()):
            with (
                self.subTest(answer=answer),
                patch(
                    "builtins.input",
                    side_effect=answer if isinstance(answer, Exception) else None,
                    return_value=answer,
                ),
                patch("academia.cli.load_config") as config,
                patch("academia.cli.notifications.report_error"),
            ):
                self.assertEqual(self.call(["--run"]), 1)
                config.assert_not_called()
