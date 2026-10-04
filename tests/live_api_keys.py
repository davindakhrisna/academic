"""Opt-in live checks: one vision request per API key, with no fallback."""

import os
import unittest

from main.config import (
    DEFAULT_MODEL,
    KEY_NAMES,
    KEY_PATTERN,
    Config,
    config_path,
    read_env,
    validate_model,
)
from main.errors import AcademicError
from main.gemini import GeminiClient
from tests.helpers import png


def settings(environ=None):
    values = dict(os.environ if environ is None else environ)
    path = config_path(values)
    if path.exists():
        values.update(read_env(path)[1])
    elif values.get("ACADEMIC_ENV_FILE") or values.get("SHELLCUT_ENV_FILE"):
        raise AcademicError("The specified configuration file does not exist.")
    return values


def probe(index, values, transport=None):
    name = KEY_NAMES[index]
    key = values.get(name, "")
    if not key or key.startswith("your_"):
        raise AcademicError(f"{name}: missing or placeholder key.")
    if not KEY_PATTERN.fullmatch(key):
        raise AcademicError(f"{name}: invalid key format.")
    model = validate_model(values.get("GEMINI_MODEL") or DEFAULT_MODEL)
    try:
        answer = GeminiClient(Config(model, (key,)), transport).generate(
            png(marker=255, width=64, height=64),
            "Identify the dominant color of this solid-color image. "
            "Reply with exactly RED, with no other text.",
            strict=True,
        )
        if answer.strip().upper() != "RED":
            raise AcademicError("Vision response did not identify the red test image.")
    except AcademicError as error:
        message = str(error)
        for secret_name in KEY_NAMES:
            if secret := values.get(secret_name):
                message = message.replace(secret, "[redacted]")
        raise AcademicError(message) from None


class LiveApiKeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values = settings()
        print("\nLive Gemini vision checks: three independent requests; quota/cost may apply.")

    def check_key(self, index):
        try:
            probe(index, self.values)
        except AcademicError as error:
            self.fail(str(error))

    def test_01_primary_key(self):
        self.check_key(0)

    def test_02_backup_key(self):
        self.check_key(1)

    def test_03_tertiary_key(self):
        self.check_key(2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
