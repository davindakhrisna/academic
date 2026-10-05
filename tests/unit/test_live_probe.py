import json
import unittest

from main.config import Config
from main.errors import AcademicError
from tests.live.router import probe
from tests.support.helpers import question, stop_screen
from tests.support.router import Transport, response


class LiveProbeTests(unittest.TestCase):
    def setUp(self):
        self.config = Config("Academic", "secret")

    def test_screenshot_probe_uses_academic_combo(self):
        transport = Transport([response("RED")])
        probe(self.config, transport)
        self.assertEqual(len(transport.calls), 1)
        model, key, raw = transport.calls[0]
        self.assertEqual(model, "Academic")
        self.assertEqual(key, "secret")
        self.assertIn(b"data:image/png;base64,", raw)

    def test_runner_probe_validates_non_question(self):
        transport = Transport([response(json.dumps(stop_screen()))])
        probe(self.config, transport, runner=True)
        payload = json.loads(transport.calls[0][2])
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        for data in (question(), {**stop_screen(), "next": question()["next"]}):
            transport = Transport([response(json.dumps(data))])
            with self.subTest(data=data), self.assertRaises(AcademicError):
                probe(self.config, transport, runner=True)
            self.assertEqual(len(transport.calls), 1)

    def test_wrong_color_does_not_expose_response(self):
        transport = Transport([response("secret")])
        with self.assertRaisesRegex(AcademicError, "Vision response") as caught:
            probe(self.config, transport)
        self.assertNotIn("secret", str(caught.exception))
