import unittest
from unittest.mock import patch

from academia import notifications
from academia.errors import AcademicError


class NotificationTests(unittest.TestCase):
    def test_markup_is_escaped_and_arguments_are_separate(self):
        with (
            patch("academia.notifications.sys.platform", "linux"),
            patch("academia.notifications.run_command") as command,
        ):
            notifications.notify("0 < x & x > 5")
        self.assertEqual(
            command.call_args.args[0][-1], "<span size='8pt'>0 &lt; x &amp; x &gt; 5</span>"
        )
        self.assertIn("--", command.call_args.args[0])

    def test_blank_notifications_fail(self):
        with self.assertRaises(AcademicError):
            notifications.notify("  \n")

    def test_desktop_failures_propagate(self):
        with (
            patch("academia.notifications.sys.platform", "linux"),
            patch("academia.notifications.run_command", side_effect=AcademicError("missing")),
            self.assertRaises(AcademicError),
        ):
            notifications.notify("A")

    def test_windows_notifies_in_console_without_linux_tools(self):
        with (
            patch("academia.notifications.sys.platform", "win32"),
            patch("builtins.print") as output,
            patch("academia.notifications.run_command") as command,
        ):
            notifications.notify("A")
        output.assert_called_once_with("A")
        command.assert_not_called()

    def test_simulation_sends_six_notifications(self):
        with (
            patch("academia.notifications.notify") as notify,
            patch("academia.notifications.time.sleep") as sleep,
        ):
            notifications.simulate()
        self.assertEqual(notify.call_count, 6)
        self.assertEqual(sleep.call_count, 6)
