"""One runner at a time, with a stop command usable from a second terminal."""

import os
import sys
from pathlib import Path

from .errors import AcademicError, Cancelled


def state_directory() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".cache"))) / "academic"
    return Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "academic"


class RunControl:
    def __init__(self, directory: Path | None = None):
        self.directory = directory or state_directory()
        self.lock = None

    def __enter__(self):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.lock = (self.directory / "runner.lock").open("a+b")
        try:
            if sys.platform == "win32":
                import msvcrt

                if self.lock.seek(0, 2) == 0:
                    self.lock.write(b"0")
                    self.lock.flush()
                self.lock.seek(0)
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                # ponytail: one runner per user, use per-display locks if needed later.
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            self.lock = None
            raise AcademicError("Another Question Runner is already running.") from None
        try:
            (self.directory / "runner.stop").unlink(missing_ok=True)
        except BaseException:
            self.lock.close()
            self.lock = None
            raise
        return self

    def check(self):
        if (self.directory / "runner.stop").exists():
            raise Cancelled()

    def __exit__(self, *_):
        if self.lock is not None:
            self.lock.close()
            self.lock = None


def request_stop(directory: Path | None = None) -> None:
    directory = directory or state_directory()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    (directory / "runner.stop").touch()
