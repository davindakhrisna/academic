"""Small, bounded calls to installed desktop tools."""

import ctypes
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager

from .errors import AcademicError


@contextmanager
def external_environment():
    """Keep bundled libraries out of the system tools we launch."""
    environment = dict(os.environ)
    frozen = getattr(sys, "frozen", False)
    windows = frozen and sys.platform == "win32"
    directory = None
    if frozen and sys.platform.startswith("linux"):
        original = environment.get("LD_LIBRARY_PATH_ORIG")
        if original is None:
            environment.pop("LD_LIBRARY_PATH", None)
        else:
            environment["LD_LIBRARY_PATH"] = original
    if windows:
        loader = getattr(ctypes, "windll", None)
        if loader is None:
            raise OSError("Windows DLL loader is unavailable.")
        directory = loader.kernel32.SetDllDirectoryW
        directory.argtypes = [ctypes.c_wchar_p]
        directory.restype = ctypes.c_int
        if not directory(None):
            raise OSError("Cannot reset the DLL search directory.")
    try:
        yield environment
    finally:
        if directory is not None:
            directory(getattr(sys, "_MEIPASS", None))


def require_commands(*commands: str) -> None:
    missing = [command for command in commands if not shutil.which(command)]
    if missing:
        raise AcademicError("Missing required commands: " + ", ".join(missing))


def run_command(args, *, input: bytes | None = None, timeout: float = 10) -> bytes:
    try:
        with external_environment() as environment:
            result = subprocess.run(
                args,
                input=input,
                capture_output=True,
                timeout=timeout,
                check=False,
                env=environment,
            )
    except subprocess.TimeoutExpired:
        raise AcademicError(f"{args[0]} timed out.") from None
    except OSError:
        raise AcademicError(f"Cannot run {args[0]}.") from None
    if result.returncode:
        raise AcademicError(f"{args[0]} failed (exit {result.returncode}).")
    return result.stdout
