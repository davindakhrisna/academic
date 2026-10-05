"""Native Windows input and foreground checks; imported only when needed."""

import ctypes
import sys
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import PureWindowsPath

from .desktop import Desktop, Window
from .errors import AcademicError
from .images import windows_grab

BROWSERS = {
    "firefox.exe",
    "chrome.exe",
    "msedge.exe",
    "brave.exe",
    "vivaldi.exe",
    "librewolf.exe",
    "zen.exe",
    "floorp.exe",
    "chromium.exe",
    "helium.exe",
}


class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class InputUnion(ctypes.Union):
    _fields_ = [("mi", MouseInput)]


class Input(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = [("type", wintypes.DWORD), ("value", InputUnion)]


class WindowsAPI:
    user32: ctypes.CDLL
    kernel32: ctypes.CDLL

    def __init__(self):
        if sys.platform != "win32":
            raise AcademicError("Native Windows input is available only on Windows.")
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
        self.user32.ClientToScreen.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
        self.user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
        self.user32.GetWindowThreadProcessId.argtypes = (
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        )
        self.user32.IsIconic.argtypes = (wintypes.HWND,)
        self.user32.SetPhysicalCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
        self.user32.SetPhysicalCursorPos.restype = wintypes.BOOL
        self.user32.GetPhysicalCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
        self.user32.GetPhysicalCursorPos.restype = wintypes.BOOL
        self.user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int)
        self.user32.SendInput.restype = wintypes.UINT
        self.kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        self.kernel32.OpenProcess.restype = wintypes.HANDLE
        self.kernel32.QueryFullProcessImageNameW.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        )
        self.kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.user32.SetProcessDpiAwarenessContext.argtypes = (ctypes.c_void_p,)
        self.user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
        # A host or executable manifest may have already set the process policy.
        # Window geometry must also opt in on the thread making each query.
        self.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        self.user32.SetThreadDpiAwarenessContext.argtypes = (ctypes.c_void_p,)
        self.user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p

    @contextmanager
    def physical_pixels(self):
        previous = self.user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        if not previous:
            raise AcademicError("Cannot enable per-monitor DPI awareness on Windows.")
        try:
            yield
        finally:
            self.user32.SetThreadDpiAwarenessContext(previous)

    def window_info(self) -> tuple[str, Window]:
        with self.physical_pixels():
            return self._window_info()

    def _window_info(self) -> tuple[str, Window]:
        handle = self.user32.GetForegroundWindow()
        if not handle or self.user32.IsIconic(handle):
            raise AcademicError("Use an unlocked Windows desktop with the browser focused.")
        process_id = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(handle, ctypes.byref(process_id))
        process = self.kernel32.OpenProcess(0x1000, False, process_id.value)
        if not process:
            raise AcademicError("Cannot inspect the focused Windows application.")
        try:
            executable = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(executable))
            if not self.kernel32.QueryFullProcessImageNameW(
                process, 0, executable, ctypes.byref(length)
            ):
                raise AcademicError("Cannot identify the focused Windows application.")
        finally:
            self.kernel32.CloseHandle(process)
        rect = wintypes.RECT()
        if not self.user32.GetClientRect(handle, ctypes.byref(rect)):
            raise AcademicError("Cannot locate the Windows browser client area.")
        origin = wintypes.POINT(rect.left, rect.top)
        corner = wintypes.POINT(rect.right, rect.bottom)
        if not self.user32.ClientToScreen(
            handle, ctypes.byref(origin)
        ) or not self.user32.ClientToScreen(handle, ctypes.byref(corner)):
            raise AcademicError("Cannot locate the Windows browser client area.")
        title = ctypes.create_unicode_buffer(8192)
        self.user32.GetWindowTextW(handle, title, len(title))
        window = Window(
            str(handle),
            (origin.x, origin.y, corner.x, corner.y),
            title.value,
        )
        return PureWindowsPath(executable.value).name.lower(), window

    def move(self, position) -> None:
        if not self.user32.SetPhysicalCursorPos(*position):
            raise AcademicError("Windows could not position the cursor.")
        actual = wintypes.POINT()
        if not self.user32.GetPhysicalCursorPos(ctypes.byref(actual)) or (actual.x, actual.y) != position:
            raise AcademicError("Cursor did not reach the expected Windows position.")

    def click(self) -> None:
        events = (Input * 2)()
        events[0].type = events[1].type = 0  # INPUT_MOUSE
        events[0].mi.dwFlags = 0x0002  # MOUSEEVENTF_LEFTDOWN
        events[1].mi.dwFlags = 0x0004  # MOUSEEVENTF_LEFTUP
        if self.user32.SendInput(2, events, ctypes.sizeof(Input)) != 2:
            # Always attempt a release if a partial injection left the button down.
            release = Input()
            release.mi.dwFlags = 0x0004
            self.user32.SendInput(1, ctypes.byref(release), ctypes.sizeof(Input))
            raise AcademicError("Windows rejected mouse input (check browser integrity level).")


class WindowsDesktop(Desktop):
    def __init__(self, api=None, grab=None, browsers=None):
        super().__init__()
        self.api = api or WindowsAPI()
        self._grab = grab or windows_grab
        self.browsers = BROWSERS if browsers is None else browsers
        if grab is None:
            try:
                import PIL.ImageGrab  # noqa: F401
            except ImportError:
                raise AcademicError(
                    "Windows capture requires Pillow: python -m pip install Pillow"
                ) from None

    def window(self) -> Window:
        application, window = self.api.window_info()
        if self.guarded and application not in self.browsers:
            raise AcademicError("The focused Windows application is not a supported browser.")
        return window

    def grab(self, bounds) -> bytes:
        return self._grab(bounds)

    def send_click(self, window: Window, position: tuple[int, int], *, check=lambda: None) -> None:
        self.api.move(position)
        if self.guarded and self.window() != window:
            raise AcademicError("Browser changed focus before the Windows click.")
        check()
        self.api.click()
