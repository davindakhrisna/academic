"""Screen coordinates and guarded input for an existing browser window."""

import json
import os
import sys
from dataclasses import dataclass, field

from .errors import AcademicError
from .images import capture_png, png_size
from .system import require_commands, run_command
from .vision import Point

BROWSER_CLASSES = {
    "firefox",
    "firefox-esr",
    "firefox-developer-edition",
    "firefox-nightly",
    "org.mozilla.firefox",
    "google-chrome",
    "google-chrome-stable",
    "google-chrome-beta",
    "google-chrome-unstable",
    "chromium",
    "chromium-browser",
    "org.chromium.chromium",
    "brave-browser",
    "brave-browser-beta",
    "com.brave.browser",
    "librewolf",
    "io.gitlab.librewolf-community",
    "zen",
    "zen-beta",
    "zen-browser",
    "app.zen_browser.zen",
    "msedge",
    "microsoft-edge",
    "microsoft-edge-dev",
    "vivaldi",
    "vivaldi-stable",
    "floorp",
    "one.ablaze.floorp",
    "helium",
    "helium-browser",
    "net.imput.helium",
}


@dataclass(frozen=True)
class Window:
    identity: str
    bounds: tuple[int, int, int, int]
    title: str


@dataclass(frozen=True)
class Frame:
    window: Window
    image: bytes = field(repr=False)

    def __post_init__(self):
        image_width, image_height = png_size(self.image)
        left, top, right, bottom = self.window.bounds
        if right <= left or bottom <= top:
            raise AcademicError("Browser window has invalid dimensions.")
        # Logical Hyprland coordinates may differ from physical screenshot pixels,
        # but both must describe the same rectangle (allow pixel rounding).
        expected = (right - left) / (bottom - top)
        if abs(image_width / image_height - expected) > max(expected * 0.02, 2 / image_height):
            raise AcademicError("Screenshot does not match the browser window geometry.")


def screen_point(window: Window, point: Point) -> tuple[int, int]:
    left, top, right, bottom = window.bounds
    if not (0 < point.x < 1000 and 0 < point.y < 1000):
        raise AcademicError("Refusing an off-screen click.")
    return (
        min(right - 1, left + round(point.x * (right - left) / 1000)),
        min(bottom - 1, top + round(point.y * (bottom - top) / 1000)),
    )


class Desktop:
    def __init__(self):
        self.identity = None

    def window(self) -> Window:
        raise NotImplementedError

    def grab(self, bounds) -> bytes:
        return capture_png(bounds)

    def capture(self) -> Frame:
        window = self.window()
        if self.identity is None:
            self.identity = window.identity
        elif window.identity != self.identity:
            raise AcademicError("Browser window changed; runner stopped.")
        image = self.grab(window.bounds)
        if self.window() != window:
            raise AcademicError("Browser moved or lost focus during capture.")
        return Frame(window, image)

    def click(self, frame: Frame, point: Point, *, check=lambda: None) -> None:
        check()
        current = self.capture()
        check()
        if current != frame:
            raise AcademicError("Browser screen changed after analysis; no click sent.")
        self.send_click(frame.window, screen_point(frame.window, point), check=check)

    def send_click(self, window: Window, position: tuple[int, int], *, check=lambda: None) -> None:
        raise NotImplementedError


class HyprlandDesktop(Desktop):
    def __init__(self):
        super().__init__()
        require_commands("hyprctl", "grim")
        if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            raise AcademicError("Question Runner must run inside your Hyprland desktop session.")

    def _json(self, command):
        try:
            return json.loads(run_command(["hyprctl", "-j", command]))
        except (ValueError, UnicodeError):
            raise AcademicError("hyprctl returned invalid window information.") from None

    def window(self) -> Window:
        data = self._json("activewindow")
        try:
            application = data["class"].lower()
            if application not in BROWSER_CLASSES:
                raise AcademicError("The focused window is not a supported browser.")
            address = data["address"]
            if (
                not isinstance(address, str)
                or not address.startswith("0x")
                or any(c not in "0123456789abcdefABCDEF" for c in address[2:])
                or len(address) <= 2
            ):
                raise ValueError
            left, top = data["at"]
            width, height = data["size"]
            if any(type(number) is not int for number in (left, top, width, height)):
                raise ValueError
            title = data["title"]
            if not isinstance(title, str):
                raise TypeError
            return Window(address, (left, top, left + width, top + height), title)
        except (KeyError, TypeError, ValueError, AttributeError):
            raise AcademicError("Cannot identify the active browser window.") from None

    def _dispatch(self, command, argument):
        result = run_command(["hyprctl", "dispatch", command, argument]).decode().strip()
        if result != "ok":
            raise AcademicError(f"Hyprland rejected {command}; no further input will be sent.")

    def send_click(self, window: Window, position: tuple[int, int], *, check=lambda: None) -> None:
        x, y = position
        self._dispatch("movecursor", f"{x} {y}")
        cursor = self._json("cursorpos")
        if not isinstance(cursor, dict) or cursor.get("x") != x or cursor.get("y") != y:
            raise AcademicError("Cursor did not reach the expected position; no click sent.")
        if self.window() != window:
            raise AcademicError("Browser changed focus before the click.")
        check()
        self._dispatch("sendshortcut", f",mouse:272,address:{window.identity}")


def create_desktop() -> Desktop:
    if sys.platform == "win32":
        from .windows import WindowsDesktop

        return WindowsDesktop()
    if sys.platform.startswith("linux"):
        return HyprlandDesktop()
    raise AcademicError("Question Runner supports Windows and Hyprland on Linux.")
