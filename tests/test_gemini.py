import json
import subprocess
import unittest
from unittest.mock import patch

from main.config import Config
from main.errors import AcademicError, ApiError
from main.gemini import CurlTransport, GeminiClient, complete_text
from tests.helpers import png


def response(parts=None, reason="STOP"):
    return {
        "candidates": [
            {
                "finishReason": reason,
                "content": {"parts": parts if parts is not None else [{"text": "A"}]},
            }
        ]
    }


class Transport:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def post(self, model, key, payload):
        self.calls.append((model, key, payload))
        result = self.replies.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class GeminiTests(unittest.TestCase):
    def test_complete_split_text_excludes_thoughts_and_trims(self):
        data = response(
            [{"text": "hidden", "thought": True}, {"text": " Option "}, {"text": "2 \n"}]
        )
        self.assertEqual(complete_text(data), "Option 2")

    def test_incomplete_and_malformed_responses_fail(self):
        for data in (
            {},
            {"candidates": []},
            {"candidates": None},
            response(reason="MAX_TOKENS"),
            response([]),
            response([{"text": "   "}]),
            response([{"text": 123}]),
            response([{"thought": True, "text": "hidden"}]),
            response([None]),
        ):
            with self.subTest(data=data), self.assertRaises(ApiError):
                complete_text(data)

    def test_three_key_fallback_order(self):
        transport = Transport([ApiError("quota", 429), ApiError("server", 503), response()])
        client = GeminiClient(Config("my-model", ("one", "two", "three")), transport)
        self.assertEqual(client.generate(png()), "A")
        self.assertEqual([call[1] for call in transport.calls], ["one", "two", "three"])

    def test_regular_solver_retries_transport_auth_and_server_errors(self):
        for status in (None, 401, 403, 429, 500, 503):
            transport = Transport([ApiError("failure", status), response()])
            client = GeminiClient(Config("model", ("one", "two")), transport)
            with self.subTest(status=status):
                self.assertEqual(client.generate(png()), "A")
                self.assertEqual(len(transport.calls), 2)

    def test_runner_stops_on_every_api_or_transport_error_without_key_rotation(self):
        for status in (None, 400, 401, 403, 404, 429, 500, 503):
            transport = Transport([ApiError("failure", status), response()])
            client = GeminiClient(Config("model", ("one", "two")), transport)
            with self.subTest(status=status), self.assertRaises(ApiError):
                client.generate(png(), strict=True)
            self.assertEqual(len(transport.calls), 1)

    def test_bad_requests_and_unknown_models_do_not_rotate_keys(self):
        for status in (400, 404):
            transport = Transport([ApiError("failure", status), response()])
            with self.subTest(status=status), self.assertRaises(ApiError):
                GeminiClient(Config("model", ("one", "two")), transport).generate(png())
            self.assertEqual(len(transport.calls), 1)

    def test_parse_error_does_not_rotate_keys(self):
        transport = Transport([{}, response()])
        with self.assertRaises(ApiError):
            GeminiClient(Config("model", ("one", "two")), transport).generate(png())
        self.assertEqual(len(transport.calls), 1)

    def test_error_messages_redact_all_configured_keys(self):
        transport = Transport([ApiError("one invalid two", 400)])
        with self.assertRaises(ApiError) as error:
            GeminiClient(Config("model", ("one", "two")), transport).generate(png())
        self.assertNotIn("one", str(error.exception))
        self.assertNotIn("two", str(error.exception))

    def test_png_payload_and_structured_response_settings(self):
        transport = Transport([response()])
        GeminiClient(Config("model", ("one",)), transport).generate(
            png(), schema={"type": "object"}, strict=True
        )
        payload = json.loads(transport.calls[0][2])
        self.assertEqual(payload["contents"][0]["parts"][0]["inlineData"]["mimeType"], "image/png")
        self.assertEqual(payload["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(payload["generationConfig"]["responseJsonSchema"], {"type": "object"})

    def test_oversized_payload_is_rejected_before_networking(self):
        transport = Transport([])
        with patch("main.gemini.REQUEST_LIMIT", 1), self.assertRaises(AcademicError):
            GeminiClient(Config("model", ("one",)), transport).generate(png())
        self.assertEqual(transport.calls, [])

    def test_invalid_image_is_rejected_before_networking(self):
        transport = Transport([])
        with self.assertRaises(AcademicError):
            GeminiClient(Config("model", ("one",)), transport).generate(b"not PNG")
        self.assertEqual(transport.calls, [])

    def test_transport_timeout_and_missing_curl(self):
        for failure in (subprocess.TimeoutExpired("curl", 125), OSError()):
            with (
                self.subTest(failure=failure),
                patch("main.gemini.subprocess.run", side_effect=failure),
                self.assertRaises(ApiError),
            ):
                CurlTransport().post("model", "one", b"{}")
