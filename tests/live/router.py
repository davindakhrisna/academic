"""Opt-in live vision checks through the configured 9Router combo."""

import unittest

from main.config import load_config
from main.errors import AcademicError
from main.router import RouterClient
from main.vision import Vision
from tests.support.helpers import png


def probe(config, transport=None, *, runner=False):
    client = RouterClient(config, transport)
    image = png(marker=255, width=64, height=64)
    if runner:
        observation = Vision(client).inspect(image)
        if observation.status != "not_question":
            raise AcademicError("Runner did not identify the test image as a non-question.")
        return
    answer = client.generate(
        image,
        "Identify the dominant color of this solid-color image. "
        "Reply with one color name only, with no other text.",
    )
    if answer.strip().upper() != "RED":
        raise AcademicError("Vision response did not identify the red test image.")


class LiveApiKeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()
        print("\nLive 9Router checks: two image requests through the configured combo.")

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
