"""Run regression checks and save machine-readable verification evidence."""

import argparse
import hashlib
import json
import platform
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class EvidenceResult(unittest.TextTestResult):
    def __init__(self, *args):
        super().__init__(*args)
        self.passed_ids = []

    def addSuccess(self, test):
        self.passed_ids.append(test.id())
        super().addSuccess(test)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "tests" / "verification.json")
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    result = unittest.TextTestRunner(verbosity=2, resultclass=EvidenceResult).run(suite)
    source_files = sorted((ROOT / "main").glob("*.py")) + [
        ROOT / "main.py",
        ROOT / "pyproject.toml",
    ]
    report = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "platform": platform.system(),
        "python": platform.python_version(),
        "tests_run": result.testsRun,
        "passed": result.testsRun - len(result.skipped) - len(result.failures) - len(result.errors),
        "failures": [{"test": test.id(), "traceback": trace} for test, trace in result.failures],
        "errors": [{"test": test.id(), "traceback": trace} for test, trace in result.errors],
        "skipped": [{"test": test.id(), "reason": reason} for test, reason in result.skipped],
        "successful": result.wasSuccessful(),
        "passed_test_ids": result.passed_ids,
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source_files
        },
        "test_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((ROOT / "tests").glob("*.py"))
        },
        "live_gemini_tested": False,
        "native_hyprland_tested": False,
        "native_windows_gui_tested": any(
            "WindowsNativeTests" in test for test in result.passed_ids
        ),
        "notes": [
            "HTTP integration uses real curl against a local HTTP server.",
            "Desktop adapter tests use mocks except the opt-in native Windows fixture.",
            "No real assessment or authenticated browser session is used.",
            "Model accuracy and live browser behavior still require validation.",
        ],
    }
    target = args.output
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Verification evidence: {target}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
