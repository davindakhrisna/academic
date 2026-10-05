"""Read simple dotenv assignments and update the model atomically."""

import os
import re
import shlex
import stat
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .errors import AcademicError

ROOT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent.parent
)
DEFAULT_MODEL = "qwen/qwen3.8-27b:free"
DEFAULT_FALLBACK_MODEL = "deepseek/deepseek-v4.1-flash"
KEY_PATTERN = re.compile(r"[A-Za-z0-9._-]+\Z")
ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
MODEL = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)?"
    r"(?::[A-Za-z0-9][A-Za-z0-9._-]*)?\Z"
)


@dataclass(frozen=True)
class Config:
    model: str
    key: str = field(repr=False)
    fallback_model: str = DEFAULT_FALLBACK_MODEL


def config_path(environ=None, root: Path = ROOT, home: Path | None = None) -> Path:
    environ = os.environ if environ is None else environ
    override = environ.get("ACADEMIC_ENV_FILE") or environ.get("SHELLCUT_ENV_FILE")
    if override:
        return Path(override).expanduser().resolve()
    local = root / ".env"
    fallback = (home or Path.home()) / "nixos-config" / ".env"
    return local if local.is_file() or not fallback.is_file() else fallback


def parse_env(text: str) -> dict[str, str]:
    values = {}
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = ASSIGNMENT.fullmatch(line)
        if not match:
            raise AcademicError(f"Invalid .env assignment on line {number}.")
        name, raw = match.groups()
        try:
            tokens = shlex.split(raw, comments=True, posix=True)
        except ValueError:
            raise AcademicError(f"Invalid .env quoting on line {number}.") from None
        if len(tokens) > 1:
            raise AcademicError(f"Quote values containing spaces in .env (line {number}).")
        values[name] = tokens[0] if tokens else ""
    return values


def read_env(path: Path) -> tuple[str, dict[str, str]]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        raise AcademicError(f"Cannot read configuration: {path}") from None
    return text, parse_env(text)


def validate_model(model: str) -> str:
    if not MODEL.fullmatch(model):
        raise AcademicError("Invalid OpenRouter model ID; use provider/model:variant.")
    return model


def load_config(environ=None, path: Path | None = None) -> Config:
    environ = os.environ if environ is None else environ
    path = config_path(environ) if path is None else path
    values = dict(environ)
    if path.exists():
        values.update(read_env(path)[1])
    elif environ.get("ACADEMIC_ENV_FILE") or environ.get("SHELLCUT_ENV_FILE"):
        raise AcademicError(f"Configuration file does not exist: {path}")
    model = validate_model(values.get("OPENROUTER_MODEL") or DEFAULT_MODEL)
    fallback = values.get("OPENROUTER_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL)
    if fallback:
        validate_model(fallback)
    key = values.get("OPENROUTER_API_KEY", "")
    if not key:
        raise AcademicError("No OpenRouter API key configured; set OPENROUTER_API_KEY in .env.")
    if not KEY_PATTERN.fullmatch(key):
        raise AcademicError("Invalid API key format in configuration.")
    if key.startswith("your_"):
        raise AcademicError("Replace placeholder API key in .env before solving.")
    return Config(model, key, fallback)


def set_model(model: str, path: Path | None = None) -> Path:
    validate_model(model)
    path = (config_path() if path is None else path).resolve()
    text = read_env(path)[0] if path.exists() else ""
    lines = [
        line
        for line in text.splitlines()
        if not (match := ASSIGNMENT.fullmatch(line)) or match[1] != "OPENROUTER_MODEL"
    ]
    updated = "\n".join([*lines, f"OPENROUTER_MODEL={model}"]) + "\n"
    parse_env(updated)
    temporary = None
    try:
        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except OSError:
        raise AcademicError(f"Cannot update configuration: {path}") from None
    finally:
        if temporary is not None and temporary.exists():
            if os.name == "nt":
                # A copied read-only bit must not prevent cleaning up a failed update.
                os.chmod(temporary, stat.S_IWRITE)
            temporary.unlink(missing_ok=True)
    return path
