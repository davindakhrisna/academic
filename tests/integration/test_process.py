import base64
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from tests.support.helpers import png

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipIf(
    os.name == "nt", "Unix SIGTERM cleanup test; Windows uses --stop or console Ctrl+C"
)
class ProcessTests(unittest.TestCase):
    def test_sigterm_terminates_pending_request_and_cleans_private_files(self):
        with tempfile.TemporaryDirectory(prefix="academic process ") as directory:
            directory = Path(directory)
            tools = directory / "bin"
            tools.mkdir()
            work = directory / "work"
            work.mkdir()
            started = directory / "started"
            config = directory / ".env"
            config.write_text("OPENROUTER_API_KEY=primary\n")
            grim = tools / "grim"
            grim.write_text(
                f"#!{sys.executable}\nimport base64,sys\nsys.stdout.buffer.write(base64.b64decode({base64.b64encode(png()).decode()!r}))\n"
            )
            curl = tools / "curl"
            curl.write_text(
                f"#!{sys.executable}\nimport pathlib,sys,time\nsys.stdin.read()\npathlib.Path({str(started)!r}).touch()\ntime.sleep(30)\n"
            )
            grim.chmod(0o755)
            curl.chmod(0o755)
            environment = dict(
                os.environ,
                ACADEMIC_ENV_FILE=str(config),
                TMPDIR=str(work),
                PATH=str(tools) + os.pathsep + os.environ.get("PATH", ""),
            )
            process = subprocess.Popen(
                [sys.executable, str(ROOT / "main.py")],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                deadline = time.monotonic() + 5
                while not started.exists() and time.monotonic() < deadline:
                    if process.poll() is not None:
                        self.fail("App exited before the pending request began")
                    time.sleep(0.02)
                self.assertTrue(started.exists(), "App did not reach HTTP request")
                self.assertTrue(list(work.iterdir()), "No private request directory was created")
                process.send_signal(signal.SIGTERM)
                stdout, stderr = process.communicate(timeout=5)
                self.assertEqual(process.returncode, 143, stderr.decode())
                self.assertIn(b"Stopped by user", stdout)
                self.assertEqual(list(work.iterdir()), [])
                self.assertNotIn(b"primary", stdout + stderr)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)
