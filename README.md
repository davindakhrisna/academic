# Academic

Python screenshot helper with **Question Runner**, which selects and
verifies answers in your existing browser. Python 3.11 or newer is required for
source runs; standalone executables include their Python runtime.

## Download and start

Download the Linux x86_64 NixOS archive and `SHA256SUMS` from the
[v0.1.0 prerelease](https://github.com/davindakhrisna/academic/releases/tag/v0.1.0).
This binary was built and smoke-tested on NixOS; it is not a portable build for
other Linux distributions. No Windows executable is included yet.

```sh
sha256sum -c SHA256SUMS
tar -xzf academic-v0.1.0-linux-x86_64-nixos.tar.gz
cd academic-v0.1.0-linux-x86_64-nixos
cp -n .env.example .env
```

Edit `.env` to set your Gemini key and model. Backup keys can be empty. Keep the
file private; it is not included in the release. Verify requirements below, then:

```sh
./academic --help
./academic --simulate
./academic --run --questions 1 --dry-run
./academic --run --questions 1
```

Start with one practice question. Press Ctrl+C in the app terminal to stop, or
run `./academic --stop` from another terminal. Helium is recognized on both
supported platforms; browser and native Windows acceptance checks remain pending.
Read [release notes](RELEASE_NOTES.md) for the verification scope and limitations.

For the executable built from this checkout, use `./dist/academic` and point it
at the existing configuration without copying your keys:

```sh
export ACADEMIC_ENV_FILE="$PWD/.env"
./dist/academic --run --questions 1 --dry-run
```

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
`pyproject.toml` also declares the installed `academic` command.

## Build a standalone executable

Build on the operating system and architecture where the app will run:

```sh
python -m pip install ".[build]"
python build.py
./dist/academic --help
```

On Windows use `py` for the build commands and `dist\academic.exe --help` to
launch it. PyInstaller does not cross-compile Windows executables from Linux.
On NixOS you can build with:

```sh
nix shell nixpkgs#python311Packages.pyinstaller -c pyinstaller \
  --noconfirm --clean --onefile --console --noupx --name academic \
  --specpath build --workpath build/work --distpath dist main.py
```

## Desktop requirements

**Linux:** `curl`, `grim`, and `notify-send`. `--clear` requires `dunstctl`.
Question Runner requires Hyprland and `hyprctl`, with support for the
`movecursor` and mouse `sendshortcut` dispatchers. Start it from a terminal in
your normal Hyprland session. Other Wayland compositors are not supported for
automated input in this version.
