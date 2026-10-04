"""Small, bounded calls to installed desktop tools."""

import shutil
import subprocess

from .errors import AcademicError


def require_commands(*commands: str) -> None:
    missing = [command for command in commands if not shutil.which(command)]
    if missing:
        raise AcademicError("Missing required commands: " + ", ".join(missing))


def run_command(args, *, input: bytes | None = None, timeout: float = 10) -> bytes:
    try:
        result = subprocess.run(
            args, input=input, capture_output=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        raise AcademicError(f"{args[0]} timed out.") from None
    except OSError:
        raise AcademicError(f"Cannot run {args[0]}.") from None
    if result.returncode:
        raise AcademicError(f"{args[0]} failed (exit {result.returncode}).")
    return result.stdout
