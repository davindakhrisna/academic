"""Package verified Linux executables with public configuration and checksums."""

import hashlib
import json
import tarfile
from pathlib import Path

from main import __version__

ROOT = Path(__file__).resolve().parent.parent


def main():
    output = ROOT / "dist" / "releases"
    output.mkdir(parents=True, exist_ok=True)
    checksums = []
    for variant, folder, evidence in (
        ("linux-x86_64", "linux", "verification-executable.json"),
        ("linux-x86_64-nixos", "nixos", "verification-executable-nixos.json"),
    ):
        binary = ROOT / "dist" / folder / "academic"
        report = ROOT / "artifacts" / "verification" / evidence
        verified = json.loads(report.read_text())
        if (
            not verified["successful"]
            or verified["executable_sha256"] != hashlib.sha256(binary.read_bytes()).hexdigest()
        ):
            raise SystemExit(f"Executable verification is missing or stale: {variant}")
        name = f"academia-v{__version__}-{variant}"
        archive = output / f"{name}.tar.gz"
        files = {
            "academic": binary,
            "README.md": ROOT / "README.md",
            ".env.example": ROOT / ".env.example",
            "docs/release-notes.md": ROOT / "docs" / "release-notes.md",
            "config/dunst/academia.conf": ROOT / "config" / "dunst" / "academia.conf",
            "verification/verification-executable.json": report,
        }
        for filename in ("verification.json", "verification-python311.json"):
            files[f"verification/{filename}"] = ROOT / "artifacts" / "verification" / filename
        with tarfile.open(archive, "w:gz") as bundle:
            for relative, source in files.items():
                bundle.add(source, arcname=f"{name}/{relative}", recursive=False)
        checksums.append(f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}")
        print(archive)
    (output / "SHA256SUMS").write_text("\n".join(checksums) + "\n")


if __name__ == "__main__":
    main()
