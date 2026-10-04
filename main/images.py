"""Capture PNGs without keeping screenshots in the repository."""

import io
import struct
import sys

from .errors import AcademicError
from .system import run_command

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_size(image: bytes) -> tuple[int, int]:
    if len(image) < 33 or image[:8] != PNG_SIGNATURE or image[12:16] != b"IHDR":
        raise AcademicError("Screen capture did not produce a PNG image.")
    width, height = struct.unpack(">II", image[16:24])
    if not width or not height:
        raise AcademicError("Screen capture has invalid dimensions.")
    return width, height


def windows_grab(bounds=None) -> bytes:
    try:
        from PIL import ImageGrab
    except ImportError:
        raise AcademicError(
            "Windows capture requires Pillow: python -m pip install Pillow"
        ) from None
    try:
        image = ImageGrab.grab(bbox=bounds, all_screens=True, include_layered_windows=True)
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        return stream.getvalue()
    except (OSError, ValueError):
        raise AcademicError(
            "Windows screen capture failed; use an unlocked desktop session."
        ) from None


def capture_png(region: tuple[int, int, int, int] | None = None) -> bytes:
    if sys.platform == "win32":
        image = windows_grab(region)
    else:
        args = ["grim", "-t", "png"]
        if region:
            left, top, right, bottom = region
            args += ["-g", f"{left},{top} {right - left}x{bottom - top}"]
        image = run_command([*args, "-"], timeout=30)
    png_size(image)
    return image
