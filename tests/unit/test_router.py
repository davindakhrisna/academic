import json
import subprocess
import unittest
from unittest.mock import patch

from main.config import Config
from main.errors import AcademicError, ApiError
from main.router import CurlTransport, RouterClient, complete_text
from tests.support.helpers import png
from tests.support.router import Transport, response


class RouterTests(unittest.TestCase):
    def test_complete_text_excludes_reasoning_and_trims(self):
        data = response(" Option 2 \n", reasoning="hidden")
        self.assertEqual(complete_text(data), "Option 2")

    def test_incomplete_and_malformed_responses_fail(self):
        for data in (
            {},
            {"choices": []},
            {"choices": None},
            response(reason="length"),
            response(reason="content_filter"),
            response(reason="tool_calls"),
            response(""),
            response("   "),
            response(123),
            response(None, reasoning="hidden"),
            response([None]),
            {"choices": [{"finish_reason": "stop", "message": None}]},
            {"choices": [{"finish_reason": "stop", "message": {"content": "A", "refusal": "no"}}]},
        ):
            with self.subTest(data=data), self.assertRaises(ApiError):
                complete_text(data)

    def test_academic_combo_is_sent_as_one_model(self):
        transport = Transport([response()])
        client = RouterClient(Config("Academic", "secret"), transport)
        self.assertEqual(client.generate(png()), "A")
        self.assertEqual(len(transport.calls), 1)
        model, key, raw = transport.calls[0]
        self.assertEqual(model, "Academic")
        self.assertEqual(key, "secret")
        self.assertNotIn("models", json.loads(raw))

    def test_custom_gateway_is_used_by_default_transport(self):
        client = RouterClient(Config("Academic", "", "http://localhost:8080/v1"))
        self.assertEqual(client.transport.endpoint, "http://localhost:8080/v1/chat/completions")

    def test_error_without_a_gateway_key_is_not_corrupted(self):
        transport = Transport([ApiError("combo unavailable", 503)])
        with self.assertRaisesRegex(ApiError, "^combo unavailable$"):
            RouterClient(Config("Academic"), transport).generate(png())

    def test_router_errors_propagate_without_retrying_single_key(self):
        for status in (None, 400, 401, 402, 403, 404, 429, 500, 503):
            transport = Transport([ApiError("router failed secret", status)])
            client = RouterClient(Config("primary-model", "secret"), transport)
            with self.subTest(status=status), self.assertRaises(ApiError) as caught:
                client.generate(png())
            self.assertEqual(caught.exception.status, status)
            self.assertEqual(str(caught.exception), "router failed [redacted]")
            self.assertEqual(len(transport.calls), 1)

    def test_incomplete_api_answers_are_rejected(self):
        for body in ({}, response(reason="length"), response(None)):
            transport = Transport([body])
            with self.subTest(body=body), self.assertRaises(ApiError):
                RouterClient(Config("model", "secret"), transport).generate(png())
            self.assertEqual(len(transport.calls), 1)

    def test_png_payload_and_structured_response_settings(self):
        transport = Transport([response()])
        RouterClient(Config("model", "secret"), transport).generate(
            png(), schema={"type": "object"}
        )
        payload = json.loads(transport.calls[0][2])
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["messages"][0]["role"], "user")
        image_url = payload["messages"][0]["content"][1]["image_url"]["url"]
        self.assertTrue(image_url.startswith("data:image/png;base64,"))
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        self.assertEqual(payload["response_format"]["json_schema"]["schema"], {"type": "object"})
        self.assertNotIn("provider", payload)

    def test_oversized_payload_is_rejected_before_networking(self):
        transport = Transport([])
        with patch("main.router.REQUEST_LIMIT", 1), self.assertRaises(AcademicError):
            RouterClient(Config("model", "secret"), transport).generate(png())
        self.assertEqual(transport.calls, [])

    def test_invalid_image_is_rejected_before_networking(self):
        transport = Transport([])
        with self.assertRaises(AcademicError):
            RouterClient(Config("model", "secret"), transport).generate(b"not PNG")
        self.assertEqual(transport.calls, [])

    def test_transport_timeout_and_missing_curl(self):
        for failure in (subprocess.TimeoutExpired("curl", 125), OSError()):
            with (
                self.subTest(failure=failure),
                patch("main.router.subprocess.run", side_effect=failure),
                self.assertRaises(ApiError),
            ):
                CurlTransport().post("one", b"{}")
