"""Opt-in live checks using one OpenRouter key and native model fallback."""

import unittest

from academia.config import load_config
from academia.errors import AcademicError
from academia.openrouter import OpenRouterClient
from academia.vision import Vision
from tests.support.helpers import png


def probe(config, transport=None, *, runner=False):
    client = OpenRouterClient(config, transport)
    image = png(marker=255, width=64, height=64)
    if runner:
        observation = Vision(client).inspect(image)
        if observation.status != "not_question":
            raise AcademicError("Runner did not identify the test image as a non-question.")
        return
    answer = client.generate(
        image,
        "Identify the dominant color of this solid-color image. "
        "Reply with exactly RED, with no other text.",
    )
    if answer.strip().upper() != "RED":
        raise AcademicError("Vision response did not identify the red test image.")


class LiveApiKeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()
        print("\nLive OpenRouter checks: two image requests; paid fallback may incur costs.")

    def check_request(self, *, runner=False):
        try:
            probe(self.config, runner=runner)
        except AcademicError as error:
            self.fail(str(error))

    def test_screenshot(self):
        self.check_request()

    def test_runner_schema(self):
        self.check_request(runner=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
