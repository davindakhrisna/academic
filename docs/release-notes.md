# Academia v0.2.1 — Linux Hyprland preview

- Renames the Python application package to `main/`, preserving `python3 main.py`,
  `python3 -m main`, and the installed `academic` command.
- Updates imports, test mocks, packaging, and Docker build paths.
- Retains dedicated test suites, the concise README, and all v0.2.0 behavior.
- Rebuilds and verifies both Linux release variants.

# Academia v0.2.0 — Linux Hyprland preview

- Linux x86_64 builds for glibc 2.31+ and NixOS; no Windows release assets.
  The NixOS build retains dependencies on Nix-store paths from its build environment.
- OpenRouter: one API key, free Qwen primary, paid DeepSeek fallback.
- One model call per new question for answers and Next coordinates.
- Screen/focus/window changes warn and continue; stalled screens are inspected again.
- Lua and legacy Hyprland dispatch support, including targeted mouse clicks.
- Academia notification identity, content-only dunst styling, and 8pt text.
- Application, test suites, tools, release docs, and verification evidence have dedicated folders.

This is a preview: real model accuracy and native browser workflows still require
practice testing. The release is verified with offline regression checks and
standalone executable tests using synthetic API keys and desktop tools. Keys,
user configuration, and screenshots are excluded from release assets.

# Academic v0.1.0 — prerelease (historical)

Academic captures a question, asks Gemini for an answer, and shows a notification.
Question Runner can select and verify single-choice or multiple-choice answers
in an existing browser, then navigate to the next question.

This first prerelease provides a Linux x86_64 executable built on NixOS and
Python source with Windows 10/11 and Linux/Hyprland desktop adapters.
The Linux binary can retain Nix store dependencies; it is not a portable build
for other Linux distributions. There is no Windows executable in this release.

## Included behavior

- Screenshot answers, notification simulation, and dunst clearing on Linux.
- Three configured Gemini keys, including dotted keys; normal helper requests
  can fall back between keys, while Question Runner stops on any API error.
- Model selection through `.env` and atomic `--set-model` updates.
- Five-second Question Runner countdown, single/multiple selection, per-click
  verification, Next navigation, count limits, dry run, and cancellation.
- Helium recognition alongside Firefox, Chrome, Edge, Brave, and other supported
  browsers. Linux recognizes `helium`, `helium-browser`, and `net.imput.helium`;
  Windows accepts `chrome.exe` and `helium.exe` for Helium.
- Standalone builds with external configuration beside the executable or through
  `ACADEMIC_ENV_FILE`. Real API keys and configuration are never packaged.

## Verification

- Python 3.11 and 3.14: 104 regression tests passed on each; two native Windows
  checks skipped in this Linux environment. Reports contain source/test hashes.
- Eight executable smoke checks passed using synthetic keys and desktop tools:
  help, invalid arguments, model updates after relocation, screenshot/answer/
  notification flow, clearing, cancellation requests, simulation, and missing
  configuration. The report records the tested executable's SHA-256.
- Ruff lint/format checks and Linux/Windows type checks passed.
- A separate opt-in live suite checks all three configured keys independently
  with a vision request. Live calls are outside the bundled offline evidence;
  user configuration and keys are not included in the release.

## Acceptance testing still required

This is a preview release, not a production certification. Real browser clicking,
Helium sessions, native Windows capture/input, multi-monitor/DPI behavior, and
academic answer accuracy still require acceptance testing.

Question Runner uses screenshots and mouse coordinates. Timers, animations,
tooltips, changed focus, and page transitions can trigger a safe stop. There is
still a small race between final inspection and input. Previously selected
answers, non-choice questions, ambiguous screens, missing Next controls, API
failures, and automatically advancing pages stop the runner. Final Submit/Finish
controls are excluded. A failed multiple selection can leave partial selections.

Use one practice question with `--dry-run` before enabling clicks. See README.md
for platform requirements, configuration, source runs, and native build commands.

## Release assets

- `academic-v0.1.0-linux-x86_64-nixos.tar.gz`: executable, README, these notes,
  placeholder `.env.example`, and verification reports.
- `SHA256SUMS`: checksum for the archive.
- GitHub's source archives correspond to the tagged release commit.
