"""Desktop notifications on Linux; console notifications on Windows."""

import html
import sys
import time

from .errors import AcademicError
from .system import run_command


def notify(text: str) -> None:
    if not text.strip():
        raise AcademicError("Cannot send an empty notification.")
    if sys.platform == "win32":
        print(text)
        return
    run_command(
        [
            "notify-send",
            "-a",
            "pyCheat",
            "-u",
            "low",
            "-t",
            "60000",
            "--",
            "",
            f"<span size='x-small'>{html.escape(text, quote=False)}</span>",
        ]
    )


def clear() -> None:
    if sys.platform == "win32":
        raise AcademicError("Desktop notification clearing is supported with dunst on Linux.")
    run_command(["dunstctl", "close-all"])
    print("Notifications cleared.")


def simulate() -> None:
    for text in (
        "∫ x² dx = x³/3 + C",
        "0 < x < 5",
        "Error: API Quota Exceeded",
        "Error: Timeout Exceeded",
        "Error: Bad Request",
        "Error: Screen Capture Failed",
    ):
        notify(text)
        time.sleep(2)


def report_error(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    try:
        notify(f"Error: {message}")
    except AcademicError:
        pass
