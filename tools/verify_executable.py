"""Smoke-check a Linux executable using synthetic configuration and desktop tools."""

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.support.helpers import png, question

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=ROOT / "dist" / "academic")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "verification" / "verification-executable.json",
    )
    args = parser.parse_args()
    binary = args.binary.resolve()
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
        config.write_text("OPENROUTER_API_KEY=AQ.synthetic_key\nOPENROUTER_MODEL=test-model\n")
        notices = directory / "notices"
        state = directory / "quiz.json"
        state.write_text(json.dumps({"question": 1, "x": 0, "y": 0, "requests": 0}))
        environment["HYPRLAND_INSTANCE_SIGNATURE"] = "synthetic"

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
            f"""import json,pathlib,sys
assert 'AQ.synthetic_key' in sys.stdin.read()
payload=json.loads(pathlib.Path(sys.argv[sys.argv.index('--data-binary')+1][1:]).read_text())
content='Option 2'
if 'response_format' in payload:
    path=pathlib.Path({str(state)!r})
    state=json.loads(path.read_text())
    state['requests']+=1
    path.write_text(json.dumps(state))
    question={question()!r}
    question['question']='Question '+str(state['question'])
    content=json.dumps(question)
output=pathlib.Path(sys.argv[sys.argv.index('--output')+1])
output.write_text(json.dumps({{'choices':[{{'finish_reason':'stop','message':{{'role':'assistant','content':content}}}}]}}))
sys.stdout.write('200')
""",
        )
        tool(
            "hyprctl",
            rf"""import json,pathlib,re,sys
path=pathlib.Path({str(state)!r})
state=json.loads(path.read_text())
args=sys.argv[1:]
if args==['-j','activewindow']:
    print(json.dumps({{'class':'firefox','address':'0xabc','at':[0,0],'size':[1000,1000],'title':'Practice'}}))
elif args==['-j','cursorpos']:
    print(json.dumps({{'x':state['x'],'y':state['y']}}))
elif args[0]=='dispatch':
    expression=args[1]
    if expression.startswith('hl.dsp.cursor.move'):
        state['x'],state['y']=map(int,re.findall(r'-?\d+',expression))
    elif expression.startswith('hl.dsp.send_shortcut'):
        if (state['x'],state['y'])==(900,900):
            state['question']+=1
    else:
        assert expression=='function() end'
    path.write_text(json.dumps(state))
    print('ok')
else:
    raise SystemExit(1)
""",
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
        assert "OPENROUTER_MODEL=smoke-model" in config.read_text()
        assert "OPENROUTER_API_KEY=AQ.synthetic_key" in config.read_text()
        check("screenshot_answer_notification_with_external_tools", [])
        assert "Option 2" in notices.read_text()
        check("clear_notifications", ["--clear"])
        check("stop_request", ["--stop"])
        assert (directory / "cache" / "academic" / "runner.stop").exists()
        check("simulation", ["--simulate"])
        assert len(notices.read_text().splitlines()) == 7
        check("runner_dry_run_without_clicks", ["--run", "--questions", "1", "--dry-run"])
        assert json.loads(state.read_text())["question"] == 1
        check("runner_two_questions_one_request_each", ["--run", "--questions", "2"])
        quiz = json.loads(state.read_text())
        assert quiz["requests"] == 3  # One dry run and two actual questions.
        assert quiz["question"] == 2  # Next is clicked once; the count limit stops navigation.
        environment["ACADEMIC_ENV_FILE"] = str(directory / "missing.env")
        check("missing_configuration", [], 1)
    report = {
        "successful": True,
        "platform": sys.platform,
        "executable_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "passed_checks": checks,
        "live_openrouter_tested": False,
        "native_desktop_tested": False,
    }
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{len(checks)} executable smoke checks passed. Evidence: {output}")


if __name__ == "__main__":
    main()
