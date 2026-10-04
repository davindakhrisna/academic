"""Build academic for the current OS without including configuration or secrets."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print('Install build dependencies first: python -m pip install ".[build]"', file=sys.stderr)
        return 1
    (ROOT / "build").mkdir(exist_ok=True)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--console",
            "--noupx",
            "--name",
            "academic",
            "--distpath",
            str(ROOT / "dist"),
            "--workpath",
            str(ROOT / "build" / "work"),
            "--specpath",
            str(ROOT / "build"),
            str(ROOT / "main.py"),
        ],
        cwd=ROOT,
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
