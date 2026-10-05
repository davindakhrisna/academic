import json
import unittest
from unittest.mock import patch

from academia.desktop import Frame, HyprlandDesktop, Window, screen_point
from academia.errors import AcademicError, Cancelled
from academia.vision import Point
from academia.windows import WindowsDesktop
from tests.support.helpers import QuizDesktop, png


class FakeWindowsAPI:
    def __init__(self):
        self.application = "firefox.exe"
        self.window = Window("12345", (-1920, 100, -920, 1100), "Practice quiz")
        self.moves = []
        self.clicks = 0
        self.after_move = None

    def window_info(self):
        return self.application, self.window

    def move(self, position):
        self.moves.append(position)
        if self.after_move:
            self.after_move()

    def click(self):
        self.clicks += 1


class DesktopTests(unittest.TestCase):
    def test_normalized_coordinates_handle_negative_monitors_and_scaling(self):
        window = Window("1", (-1920, 100, -920, 1100), "browser")
        self.assertEqual(screen_point(window, Point(500, 500)), (-1420, 600))
        self.assertEqual(screen_point(window, Point(100, 200)), (-1820, 300))
        with self.assertRaises(AcademicError):
            screen_point(window, Point(1000, 100))

    def test_invalid_capture_and_empty_bounds_fail(self):
        for image, bounds in ((b"bad", (0, 0, 1, 1)), (png(), (0, 0, 0, 1))):
            with self.subTest(bounds=bounds), self.assertRaises(AcademicError):
                Frame(Window("1", bounds, "browser"), image)

    def test_window_changed_after_analysis_sends_no_input(self):
        desktop = QuizDesktop()
        frame = desktop.capture()
        desktop.active = Window("other", frame.window.bounds, "Other browser")
        with self.assertRaises(AcademicError):
            desktop.click(frame, Point(100, 100))
        self.assertFalse(desktop.clicks)

    def test_window_moving_during_capture_fails(self):
        desktop = QuizDesktop()
        desktop.after_capture = lambda: setattr(
            desktop, "active", Window("browser", (0, 0, 500, 500), "quiz")
        )
        with self.assertRaisesRegex(AcademicError, "during capture"):
            desktop.capture()

    def test_windows_adapter_converts_coordinates_and_clicks(self):
        api = FakeWindowsAPI()
        desktop = WindowsDesktop(api=api, grab=lambda bounds: png())
        desktop.click(desktop.capture(), Point(100, 200))
        self.assertEqual(api.moves, [(-1820, 300)])
        self.assertEqual(api.clicks, 1)

    def test_windows_non_browser_is_rejected(self):
        api = FakeWindowsAPI()
        api.application = "notepad.exe"
        with self.assertRaisesRegex(AcademicError, "not a supported browser"):
            WindowsDesktop(api=api, grab=lambda bounds: png()).capture()

    def test_windows_helium_identifiers_capture_and_click(self):
        for application in ("chrome.exe", "helium.exe"):
            with self.subTest(application=application):
                api = FakeWindowsAPI()
                api.application = application
                desktop = WindowsDesktop(api=api, grab=lambda bounds: png())
                desktop.click(desktop.capture(), Point(100, 200))
                self.assertEqual(api.clicks, 1)

    def test_hyprland_helium_identifiers_are_recognized_exactly(self):
        for application in ("helium", "Helium", "helium-browser", "net.imput.helium"):
            active = {
                "class": application,
                "address": "0xabc",
                "at": [0, 0],
                "size": [1000, 1000],
                "title": "Practice quiz",
            }
            with (
                self.subTest(application=application),
                patch("academia.desktop.require_commands"),
                patch.dict("os.environ", {"HYPRLAND_INSTANCE_SIGNATURE": "test"}),
                patch("academia.desktop.run_command", return_value=json.dumps(active).encode()),
            ):
                desktop = HyprlandDesktop()
                desktop.grab = lambda bounds: png()
                self.assertEqual(desktop.capture().window.identity, "0xabc")

    def test_helium_substring_in_another_application_is_rejected(self):
        api = FakeWindowsAPI()
        api.application = "terminal-helium.exe"
        with self.assertRaises(AcademicError):
            WindowsDesktop(api=api, grab=lambda bounds: png()).capture()
        active = {"class": "terminal-helium"}
        with (
            patch("academia.desktop.require_commands"),
            patch.dict("os.environ", {"HYPRLAND_INSTANCE_SIGNATURE": "test"}),
            patch("academia.desktop.run_command", return_value=json.dumps(active).encode()),
            self.assertRaises(AcademicError),
        ):
            HyprlandDesktop().window()

    def test_windows_focus_change_after_motion_sends_no_click(self):
        api = FakeWindowsAPI()
        desktop = WindowsDesktop(api=api, grab=lambda bounds: png())
        frame = desktop.capture()
        api.after_move = lambda: setattr(api, "application", "notepad.exe")
        with self.assertRaises(AcademicError):
            desktop.click(frame, Point(100, 200))
        self.assertEqual(api.clicks, 0)

    def test_unguarded_windows_accepts_non_browser_and_focus_changes(self):
        api = FakeWindowsAPI()
        api.application = "notepad.exe"
        desktop = WindowsDesktop(api=api, grab=lambda bounds: png())
        desktop.guarded = False
        frame = desktop.capture()
        api.after_move = lambda: setattr(api, "window", Window("other", api.window.bounds, "Other"))
        desktop.click(frame, Point(100, 200))
        self.assertEqual(api.clicks, 1)

    def test_windows_stop_after_motion_sends_no_click(self):
        api = FakeWindowsAPI()
        desktop = WindowsDesktop(api=api, grab=lambda bounds: png())
        stopped = [False]
        api.after_move = lambda: stopped.__setitem__(0, True)

        def check():
            if stopped[0]:
                raise Cancelled()

        with self.assertRaises(Cancelled):
            desktop.click(desktop.capture(), Point(100, 200), check=check)
        self.assertEqual(api.clicks, 0)

    def test_hyprland_requires_a_desktop_session(self):
        with (
            patch("academia.desktop.require_commands"),
            patch.dict("os.environ", {}, clear=True),
            self.assertRaisesRegex(AcademicError, "desktop session"),
        ):
            HyprlandDesktop()

    def test_hyprland_non_browser_name_cannot_pass_by_substring(self):
        active = {
            "class": "terminal-firefox",
            "address": "0xabc",
            "at": [0, 0],
            "size": [1000, 1000],
            "title": "Not a browser",
        }
        with (
            patch("academia.desktop.require_commands"),
            patch.dict("os.environ", {"HYPRLAND_INSTANCE_SIGNATURE": "test"}),
            patch("academia.desktop.run_command", return_value=json.dumps(active).encode()),
            self.assertRaisesRegex(AcademicError, "not a supported browser"),
        ):
            HyprlandDesktop().window()

    def test_hyprland_motion_and_targeted_mouse_dispatch(self):
        calls = []
        active = {
            "class": "firefox",
            "address": "0xabc",
            "at": [0, 0],
            "size": [1000, 1000],
            "title": "quiz",
        }

        def command(args):
            calls.append(args)
            if args[1:] == ["-j", "activewindow"]:
                return json.dumps(active).encode()
            if args[1:] == ["-j", "cursorpos"]:
                return b'{"x":100,"y":200}'
            return b"ok\n"

        probe = ["hyprctl", "dispatch", "function() end"]
        for lua in (False, True):
            calls.clear()

            def dispatch(args, lua=lua):
                if args == probe:
                    calls.append(args)
                    return b"ok" if lua else b"Invalid dispatcher"
                return command(args)

            with (
                self.subTest(lua=lua),
                patch("academia.desktop.require_commands"),
                patch.dict("os.environ", {"HYPRLAND_INSTANCE_SIGNATURE": "test"}),
                patch("academia.desktop.run_command", side_effect=dispatch),
            ):
                desktop = HyprlandDesktop()
                desktop.grab = lambda bounds: png()
                desktop.click(desktop.capture(), Point(100, 200))
            self.assertEqual(calls.count(probe), 1)
            move = ["hl.dsp.cursor.move({x=100,y=200})"] if lua else ["movecursor", "100 200"]
            click = (
                ['hl.dsp.send_shortcut({mods="",key="mouse:272",window="address:0xabc"})']
                if lua
                else ["sendshortcut", ",mouse:272,address:0xabc"]
            )
            self.assertIn(["hyprctl", "dispatch", *move], calls)
            self.assertIn(["hyprctl", "dispatch", *click], calls)

    def test_hyprland_unknown_dispatch_syntax_sends_no_input(self):
        with (
            patch("academia.desktop.require_commands"),
            patch.dict("os.environ", {"HYPRLAND_INSTANCE_SIGNATURE": "test"}),
            patch("academia.desktop.run_command", return_value=b"unexpected response") as command,
        ):
            desktop = HyprlandDesktop()
            with self.assertRaisesRegex(AcademicError, "dispatch syntax"):
                desktop.send_click(Window("0xabc", (0, 0, 1000, 1000), "quiz"), (100, 200))
        command.assert_called_once_with(["hyprctl", "dispatch", "function() end"])

    def test_hyprland_wrong_cursor_position_prevents_click(self):
        active = {
            "class": "firefox",
            "address": "0xabc",
            "at": [0, 0],
            "size": [1000, 1000],
            "title": "quiz",
        }
        calls = []

        def command(args):
            calls.append(args)
            if "activewindow" in args:
                return json.dumps(active).encode()
            if "cursorpos" in args:
                return b'{"x":0,"y":0}'
            return b"ok"

        with (
            patch("academia.desktop.require_commands"),
            patch.dict("os.environ", {"HYPRLAND_INSTANCE_SIGNATURE": "test"}),
            patch("academia.desktop.run_command", side_effect=command),
        ):
            desktop = HyprlandDesktop()
            desktop.grab = lambda bounds: png()
            with self.assertRaisesRegex(AcademicError, "Cursor"):
                desktop.click(desktop.capture(), Point(100, 200))
        self.assertFalse(any("mouse:272" in arg for call in calls for arg in call))
