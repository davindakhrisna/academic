# Academia

Screenshot answers and an automatic question runner for **Linux Hyprland**.
Python source requires 3.11+. Requests use a local 9Router gateway.

## Start

1. Install `curl`, `grim`, `hyprctl`, and `notify-send`; run inside Hyprland.
2. Start 9Router and create a combo named `Academic` containing models that support
   image input. Configure their connections and fallback order in 9Router.
3. Copy `.env.example` to `.env`. Set `ROUTER_API_KEY` to a **9Router gateway key**
   if gateway authentication is enabled; otherwise leave it empty.

Use the Python source for this migration. Previously published v0.2.1 binaries
still use the old OpenRouter configuration; build a new executable with `tools.build`
to use 9Router without Python on the target machine.

```dotenv
ROUTER_BASE_URL=http://127.0.0.1:20128/v1
ROUTER_MODEL=Academic
ROUTER_API_KEY=
```

The app sends `model: "Academic"`; 9Router selects models and handles fallbacks.
Provider keys belong in 9Router, not this app. To change the combo, use
`python3 main.py --set-model COMBO`. Upstream provider quotas and costs still apply.

```sh
python3 main.py --run --questions 1 --dry-run  # Read a practice question without clicking
python3 main.py --run --questions 5           # Answer and advance automatically
python3 main.py --stop                        # Stop from another terminal
python3 main.py                              # Screenshot answer as a notification
```

Keep `.env` beside the executable, or set `ACADEMIC_ENV_FILE` to its path.
Ctrl+C also stops the runner. For source runs, use `python3 main.py` with the
same arguments, or `python3 -m main`.

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

`main/` contains the app; `tests/` separates unit, integration, live, native,
and support files; `tools/` holds build/verification commands; `artifacts/verification/`
holds evidence. Live API checks are opt-in: `python3 -m tests.live.router`.
They make two image requests through the configured combo and may incur provider
costs. See [release notes](docs/release-notes.md).
