"""Physical screenshot-to-input coordinates without a Windows desktop."""

import ctypes
import unittest
from unittest.mock import Mock, patch

from main.errors import AcademicError
from main.vision import Point
from main.windows import WindowsAPI, WindowsDesktop
from tests.support.helpers import png


class WindowsCoordinateTests(unittest.TestCase):
    def make_api(self, scale=1, process_policy_locked=False):
        user32, kernel32 = Mock(), Mock()
        state = {"context": -2, "cursor": (0, 0)}

        def context(value):
            previous = state["context"]
            state["context"] = (
                ctypes.c_ssize_t(value.value).value if isinstance(value, ctypes.c_void_p) else value
            )
            return previous

        def client_rect(handle, result):
            factor = 1 if state["context"] == -4 else scale
            rect = result._obj
            rect.left = rect.top = 0
            rect.right, rect.bottom = round(1200 / factor), round(800 / factor)
            return True

        def to_screen(handle, result):
            factor = 1 if state["context"] == -4 else scale
            result._obj.x += round(-1920 / factor)
            result._obj.y += round(100 / factor)
            return True

        def executable(handle, flags, result, length):
            result.value = r"C:\Program Files\Microsoft\Edge\msedge.exe"
            return True

        def move(x, y):
            state["cursor"] = (x, y)
            return True

        def cursor(result):
            result._obj.x, result._obj.y = state["cursor"]
            return True

        user32.SetProcessDpiAwarenessContext.return_value = not process_policy_locked
        user32.SetThreadDpiAwarenessContext.side_effect = context
        user32.GetForegroundWindow.return_value = 123
        user32.IsIconic.return_value = False
        user32.GetClientRect.side_effect = client_rect
        user32.ClientToScreen.side_effect = to_screen
        user32.SetPhysicalCursorPos.side_effect = move
        user32.GetPhysicalCursorPos.side_effect = cursor
        user32.SendInput.return_value = 2
        kernel32.QueryFullProcessImageNameW.side_effect = executable
        with (
            patch("main.windows.sys.platform", "win32"),
            patch("main.windows.ctypes.WinDLL", side_effect=[user32, kernel32], create=True),
        ):
            api = WindowsAPI()
        return api, user32, state

    def test_scaled_monitors_and_locked_manifest_use_physical_pixels(self):
        for scale in (1, 1.25, 1.5, 2):
            for locked in (False, True):
                with self.subTest(scale=scale, locked=locked):
                    api, user32, state = self.make_api(scale, locked)
                    desktop = WindowsDesktop(
                        api=api, grab=lambda bounds: png(width=1200, height=800)
                    )
                    frame = desktop.capture()
                    self.assertEqual(frame.window.bounds, (-1920, 100, -720, 900))
                    desktop.click(frame, Point(500, 750))
                    self.assertEqual(state["cursor"], (-1320, 700))
                    self.assertEqual(state["context"], -2)
                    user32.SetCursorPos.assert_not_called()
                    user32.GetCursorPos.assert_not_called()
                    user32.SendInput.assert_called_once()

    def test_context_is_applied_again_after_host_changes_thread_policy(self):
        api, _, state = self.make_api(1.5, True)
        api.window_info()
        state["context"] = -1
        self.assertEqual(api.window_info()[1].bounds, (-1920, 100, -720, 900))
        self.assertEqual(state["context"], -1)

    def test_failed_geometry_restores_host_context(self):
        api, user32, state = self.make_api()
        user32.GetClientRect.side_effect = None
        user32.GetClientRect.return_value = False
        with self.assertRaisesRegex(AcademicError, "client area"):
            api.window_info()
        self.assertEqual(state["context"], -2)

    def test_failed_dpi_context_does_not_query_geometry(self):
        api, user32, _ = self.make_api()
        user32.SetThreadDpiAwarenessContext.side_effect = None
        user32.SetThreadDpiAwarenessContext.return_value = None
        with self.assertRaisesRegex(AcademicError, "DPI awareness"):
            api.window_info()
        user32.GetClientRect.assert_not_called()

    def test_clipped_physical_cursor_sends_no_click(self):
        api, user32, _ = self.make_api()
        user32.SetPhysicalCursorPos.side_effect = None
        user32.SetPhysicalCursorPos.return_value = True
        desktop = WindowsDesktop(api=api, grab=lambda bounds: png(width=1200, height=800))
        with self.assertRaisesRegex(AcademicError, "expected Windows position"):
            desktop.click(desktop.capture(), Point(500, 500))
        user32.SendInput.assert_not_called()
