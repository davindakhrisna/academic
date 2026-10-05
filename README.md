# Academia

Screenshot answers and an automatic question runner for **Linux Hyprland**.
This release ships Linux x86_64 binaries only. Python source requires 3.11+.

## Start

1. Install `curl`, `grim`, `hyprctl`, and `notify-send`; run inside Hyprland.
2. Download [v0.2.0](https://github.com/davindakhrisna/academic/releases/tag/v0.2.0).
   Use the `linux-x86_64` archive on glibc 2.31+ systems, or the `linux-x86_64-nixos`
   archive on NixOS. Extract it and keep the files together.
3. Copy `.env.example` to `.env`, then set `OPENROUTER_API_KEY`.

The NixOS binary retains Nix-store runtime dependencies; use the Python source
if those paths are unavailable. Check downloads with `sha256sum -c SHA256SUMS`.

```dotenv
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=qwen/qwen3.8-27b:free
OPENROUTER_FALLBACK_MODEL=deepseek/deepseek-v4.1-flash
```

One key serves both models. DeepSeek is a **paid fallback** and needs credits;
leave `OPENROUTER_FALLBACK_MODEL=` empty to disable it.

```sh
./academic --run --questions 1 --dry-run  # Read a practice question without clicking
./academic --run --questions 5           # Answer and advance automatically
./academic --stop                        # Stop from another terminal
./academic                              # Screenshot answer as a notification
```

Keep `.env` beside the executable, or set `ACADEMIC_ENV_FILE` to its path.
Ctrl+C also stops the runner. For source runs, use `python3 main.py` with the
same arguments, or `python3 -m academia`.

## Runner behavior

Each new question uses one API call for answers and Next coordinates. The runner
selects answers and clicks Next until the count is reached; it never clicks a
final Submit/Finish button. Selections are not verified by another model call.

Screen changes, focus loss, window moves, and window switches warn and continue.
Coordinates are applied to the current window, so moved controls can receive a
wrong click. Ambiguous or stalled screens are inspected again, making extra API
calls. No-question/results screens, cancellation, the count limit, and API/input
failures end the run.

Optional content-only, pale, transparent notifications: copy
`config/dunst/academia.conf` into `~/.config/dunst/dunstrc.d/` and run
`dunstctl reload`. Home Manager services with an explicit config need the rule
included in their dunst configuration. Notification text uses 8pt.

## Develop

```sh
python3 -m tools.verify              # Offline unit, integration, and native checks
python3 -m unittest discover -s tests/unit -t .
python3 -m tools.build              # Requires: python3 -m pip install ".[build]"
```

A portable Linux build uses Docker:

```sh
mkdir -p dist/linux
docker build -f tools/Dockerfile.linux -t academia-builder .
docker run --rm -v "$PWD/dist/linux:/out" academia-builder
```

`academia/` contains the app; `tests/` separates unit, integration, live, native,
and support files; `tools/` holds build/verification commands; `artifacts/verification/`
holds evidence. Live API checks are opt-in: `python3 -m tests.live.openrouter`.
They may use the paid fallback. See [release notes](docs/release-notes.md).
