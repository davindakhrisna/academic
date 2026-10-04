"""Smoke-check a Linux executable using synthetic configuration and desktop tools."""

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.helpers import png

ROOT = Path(__file__).resolve().parent.parent


def main():
    binary = ROOT / "dist" / "academic"
    checks = []
    with tempfile.TemporaryDirectory(prefix="academic-binary-") as temporary:
        directory = Path(temporary)
        copied = directory / "academic"
        shutil.copy2(binary, copied)
        commands = directory / "commands"
        commands.mkdir()
        environment = dict(os.environ, PATH=str(commands), XDG_CACHE_HOME=str(directory / "cache"))
        for name in ("ACADEMIC_ENV_FILE", "SHELLCUT_ENV_FILE"):
            environment.pop(name, None)
        config = directory / ".env"
        config.write_text("GOOGLE_API_KEY=AQ.synthetic_key\nGEMINI_MODEL=test-model\n")
        notices = directory / "notices"

        def tool(name, body):
            path = commands / name
            path.write_text(f"#!{sys.executable}\n" + body)
            path.chmod(0o755)

        tool(
            "grim",
            f"import base64,sys\nsys.stdout.buffer.write(base64.b64decode({base64.b64encode(png()).decode()!r}))\n",
        )
        tool(
            "notify-send",
            f"import pathlib,sys\nwith pathlib.Path({str(notices)!r}).open('a') as stream: stream.write(sys.argv[-1]+'\\n')\n",
        )
        tool("dunstctl", "import sys\nassert sys.argv[1:] == ['close-all']\n")
        tool(
            "curl",
            "import json,pathlib,sys\nassert 'AQ.synthetic_key' in sys.stdin.read()\noutput=pathlib.Path(sys.argv[sys.argv.index('--output')+1])\noutput.write_text(json.dumps({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'Option 2'}]}}]}))\nsys.stdout.write('200')\n",
        )

        def check(name, args, expected=0):
            result = subprocess.run(
                [str(copied), *args],
                cwd=ROOT.parent,
                env=environment,
                capture_output=True,
                timeout=30,
                check=False,
            )
            assert result.returncode == expected, (name, result.returncode, result.stderr.decode())
            assert b"AQ.synthetic_key" not in result.stdout + result.stderr
            checks.append(name)
            return result

        assert b"--run" in check("help_without_python_on_path", ["--help"]).stdout
        check("invalid_arguments", ["--questions", "0"], 2)
        check(
            "model_update_beside_executable_from_another_directory", ["--set-model", "smoke-model"]
        )
        assert "GEMINI_MODEL=smoke-model" in config.read_text()
        assert "GOOGLE_API_KEY=AQ.synthetic_key" in config.read_text()
        check("screenshot_answer_notification_with_external_tools", [])
        assert "Option 2" in notices.read_text()
        check("clear_notifications", ["--clear"])
        check("stop_request", ["--stop"])
        assert (directory / "cache" / "academic" / "runner.stop").exists()
        check("simulation", ["--simulate"])
        assert len(notices.read_text().splitlines()) == 7
        environment["ACADEMIC_ENV_FILE"] = str(directory / "missing.env")
        check("missing_configuration", [], 1)
    report = {
        "successful": True,
        "platform": sys.platform,
        "executable_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "passed_checks": checks,
        "live_gemini_tested": False,
        "native_desktop_tested": False,
    }
    output = ROOT / "tests" / "verification-executable.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{len(checks)} executable smoke checks passed. Evidence: {output}")


if __name__ == "__main__":
    main()
