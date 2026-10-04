# Academic

A modular Python screenshot helper with **Question Runner**, which selects and
verifies answers in your existing browser. The application has not been compiled
into an executable. Python 3.11 or newer is required.

## Run from source

From this directory:

```sh
python main.py                         # Screenshot, Gemini answer, notification
python main.py --simulate
python main.py --clear                 # Linux/dunst
python main.py --notify '0 < x < 5'
python main.py --set-model gemini-3.8-flash
python main.py --run                   # Prompt for question count, then countdown
python main.py --run --questions 10
python main.py --run --questions 1 --dry-run
python main.py --stop                  # From a second terminal
```

`python -m main` accepts the same arguments. `py main.py` can be used on
Windows. `main.sh` is a small compatibility launcher for Linux shortcuts.
`pyproject.toml` declares the future `academic` command; no package installation
or executable build has been performed as part of this migration.

## Configuration

Keep your existing `.env`; do not overwrite it with the example. Settings are:

```dotenv
GOOGLE_API_KEY=your_primary_key
GOOGLE_API_KEY_BACKUP=your_backup_key
GOOGLE_API_KEY_TERTIARY=your_tertiary_key
GEMINI_MODEL=gemini-3.8-flash
```

Backup keys may be empty. Replace the example keys before solving.
Configuration comes from this directory's `.env`, then `~/nixos-config/.env`.
`ACADEMIC_ENV_FILE` selects an explicit path; `SHELLCUT_ENV_FILE` is still
accepted for compatibility. File settings override environment variables.

The Python parser supports single-line assignments, `export`, quoted values,
blank lines, and comments. It never executes shell code or expands `$VARIABLE`
or `$(commands)`. Quote values containing spaces. This intentionally differs
from sourcing a Bash file.

Model updates use an atomic replacement, preserve other assignments/comments,
follow symlinks, and preserve existing permission bits. New files use mode 600
on Linux; Windows uses the destination directory's ACLs. A changed model takes
effect on the next invocation, including the next Question Runner session.
Avoid editing the same `.env` concurrently with `--set-model`.

The default is [`gemini-3.8-flash`](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash),
which Google lists as stable with image input and reasoning support. Account
availability and accuracy on your questions must still be checked live.

## Desktop requirements

**Linux:** `curl`, `grim`, and `notify-send`. `--clear` requires `dunstctl`.
Question Runner requires Hyprland and `hyprctl`, with support for the
`movecursor` and mouse `sendshortcut` dispatchers. Start it from a terminal in
your normal Hyprland session. Other Wayland compositors are not supported for
automated input in this version.

**Windows 10/11:** Python, `curl.exe` (included in current Windows versions),
and Pillow:

```powershell
py -m pip install "Pillow>=11"
```

Question Runner uses native Windows APIs for foreground-window checks, physical
pixel coordinates, cursor positioning, and mouse input. The desktop must be
unlocked; use the same privilege level as your browser. Supported browser
processes include Firefox, Chrome, Edge, Brave, Chromium, Vivaldi, LibreWolf,
Zen, and Floorp. Windows notifications currently print in the console;
system-wide notification clearing remains Linux/dunst only.

## Question Runner behavior

1. Enter the number of questions, then switch to your browser during the
   five-second countdown. No input is sent during this countdown.
2. The runner captures the focused browser client/window area and asks Gemini
   to identify and solve one fully visible multiple-choice question.
3. It validates the response, supports radio buttons and multiple checkboxes,
   and refuses unknown, duplicate, disabled, or off-screen actions.
4. Immediately before every click, it checks that the browser window and PNG
   still match the analyzed snapshot. If the screen changed, it stops.
5. It captures and inspects the result after each selected control. Only a
   verified selection counts as answered. Failed, inconsistent, or unexpected selections stop
   the run; clicks are never blindly retried.
6. It clicks an enabled, explicitly identified **Next question** control,
   then repeats. It stops at the requested count without clicking Next again.

It also stops on non-question screens, free-text answers, ambiguous or incomplete
questions, multiple visible questions, results pages, existing selected answers,
graded questions, repeated questions, lost focus, missing Next controls, invalid
AI output, or any API/transport error. **Runner requests do not rotate API keys
after a quota error or any other failure.** The normal screenshot helper retains
the three-key fallback for transport errors, 401/403/429, and server errors.

If a failure happens partway through multiple selection, those already selected
controls are left as they are. The runner stops and does not toggle them again.

Ctrl+C stops the source process. `--stop` asks the current user's runner to
stop at its next cancellation check, before any subsequent click. A network
request already in progress may take up to its timeout to return. One runner
is allowed per user/cache directory. During a run, leave the browser visible
and avoid typing, scrolling, moving windows, or changing tabs.

`--dry-run` performs the countdown and first inspection, prints the proposed
answers, and sends no mouse input. Final Submit/Finish controls are never part
of the allowed navigation. Pages that automatically advance after a selection
are not supported: the runner cannot verify the original question after that
transition and stops.

Screen capture is lossless PNG. Serialized inline requests are capped at 20 MB;
responses at 4 MiB. Each HTTP request has a 10-second connection timeout and a
120-second total timeout, plus a Python process timeout. Screenshots/payloads
are held in memory or private temporary directories and cleaned up on graceful exit.
Keys are passed to curl through stdin and excluded from process arguments and
configuration representations. curl's inherited user settings are disabled.

Verification requires additional model calls: normally two per single-choice
question, or one plus the number of selected answers for multiple selection.
This affects latency, cost, and quota. Keys in the same Google project may share
quota.

## Verification

```sh
python tests/verify.py
```

This runs the standard-library unittest suite and writes `tests/verification.json`
with counts, passed test IDs, source hashes, failures, skips, platform, and the
limits of the evidence. Coverage
includes configuration and model updates, CLI routing, notifications, countdown,
single/multiple selection, navigation limits, cancellation, stale screenshots,
focus changes, quota/error termination, HTTP authentication, and payload parsing.
HTTP integration uses real curl against a local server with synthetic keys.
A full runner test combines real HTTP, structured output parsing, and a simulated
practice quiz. Unix tests also send a real SIGTERM during an in-flight request
and check temporary-file cleanup.

To exercise real Windows screenshot/input against a local Tk practice fixture:

```powershell
$env:ACADEMIC_WINDOWS_GUI_TESTS = "1"
py tests/verify.py
```

The Windows fixture verifies native radio selection, multiple checkboxes,
navigation, PNG dimensions, and input structure size. It substitutes the model;
it does not answer real questions or use an authenticated browser session.
The suite can run locally on Linux and Windows. No GitHub Actions workflow is
present in the current checkout; native Windows validation remains pending.

Passing offline tests does **not** prove Gemini's answers or coordinates are
correct. Screen-only automation still has a small race between final inspection
and input. Exact snapshot checks can stop on animations, timers, and tooltips;
that behavior is intentional. Native Windows tests cannot be executed from
Linux. Live model evaluation, actual browser forms, multi-monitor/DPI behavior,
and your desktop session still need acceptance testing before calling this
production ready.

## Modules

`cli.py` handles routing. `config.py` owns settings and model updates;
`notifications.py` owns notifications; `gemini.py` owns bounded requests and key
fallback; `vision.py` validates structured decisions; `runner.py` owns the loop;
`desktop.py` and `windows.py` own guarded platform input; `control.py` owns
cancellation/locking; `images.py` owns PNG capture. Tests exercise these same
interfaces without substituting the runner's implementation.
