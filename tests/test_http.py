import base64
import json
import os
import shutil
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from main.config import Config
from main.errors import ApiError
from main.gemini import CurlTransport, GeminiClient
from main.runner import QuestionRunner
from main.vision import Vision
from tests.helpers import QuizDesktop, png, question
from tests.test_gemini import response


@unittest.skipUnless(shutil.which("curl"), "real curl integration requires curl")
class HttpTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.replies = []
        requests, replies = self.requests, self.replies

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                requests.append((self.path, dict(self.headers), body))
                code, data = replies.pop(0)
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(data if isinstance(data, bytes) else json.dumps(data).encode())

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.endpoint = f"http://127.0.0.1:{self.server.server_port}/v1beta/models"
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.environment = patch.dict(
            os.environ,
            {"NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1", "CURL_HOME": self.temp.name},
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def client(self):
        return GeminiClient(
            Config("test-model", ("primary", "backup", "tertiary")), CurlTransport(self.endpoint)
        )

    def test_real_post_auth_png_payload_and_three_key_fallback(self):
        self.replies[:] = [
            (429, {"error": {"message": "quota"}}),
            (503, {"error": {"message": "server"}}),
            (
                200,
                response([{"thought": True, "text": "hidden"}, {"text": "Option "}, {"text": "2"}]),
            ),
        ]
        Path(self.temp.name, ".curlrc").write_text(f'url = "{self.endpoint}/unexpected"\n')
        self.assertEqual(self.client().generate(png()), "Option 2")
        self.assertEqual(len(self.requests), 3)
        for index, (path, headers, body) in enumerate(self.requests):
            self.assertEqual(path, "/v1beta/models/test-model:generateContent")
            self.assertEqual(headers["x-goog-api-key"], ("primary", "backup", "tertiary")[index])
            self.assertEqual(headers["Content-Type"], "application/json")
            image = json.loads(body)["contents"][0]["parts"][0]["inlineData"]
            self.assertEqual(image["mimeType"], "image/png")
            self.assertEqual(base64.b64decode(image["data"]), png())

    def test_runner_quota_stops_after_one_real_request(self):
        self.replies[:] = [(429, {"error": {"message": "quota"}})]
        with self.assertRaises(ApiError) as error:
            self.client().generate(png(), strict=True)
        self.assertEqual(error.exception.status, 429)
        self.assertEqual(len(self.requests), 1)

    def test_non_json_404_does_not_retry(self):
        self.replies[:] = [(404, b"<html>not found</html>")]
        with self.assertRaises(ApiError) as error:
            self.client().generate(png())
        self.assertEqual(error.exception.status, 404)
        self.assertEqual(len(self.requests), 1)

    def test_malformed_success_stops_runner(self):
        self.replies[:] = [(200, b"not JSON")]
        with self.assertRaises(ApiError):
            self.client().generate(png(), strict=True)
        self.assertEqual(len(self.requests), 1)

    def test_full_question_runner_with_real_http_and_structured_vision(self):
        states = [
            question(1),
            question(1, selected=("2",)),
            question(2, mode="multi", answers=("1", "3")),
            question(2, mode="multi", answers=("1", "3"), selected=("1",)),
            question(2, mode="multi", answers=("1", "3"), selected=("1", "3")),
        ]
        self.replies[:] = [(200, response([{"text": json.dumps(state)}])) for state in states]
        desktop = QuizDesktop([states[0], states[2]])
        result = QuestionRunner(
            desktop, Vision(self.client()), sleep=lambda _: None, progress=lambda _: None
        ).run(2)
        self.assertTrue(result.complete)
        self.assertEqual(desktop.clicks, [(100, 200), (900, 900), (100, 100), (100, 300)])
        self.assertEqual(len(self.requests), 5)
        for _, headers, raw in self.requests:
            payload = json.loads(raw)
            self.assertEqual(headers["x-goog-api-key"], "primary")
            self.assertEqual(payload["generationConfig"]["responseMimeType"], "application/json")
            self.assertIn(
                "options", payload["generationConfig"]["responseJsonSchema"]["properties"]
            )

    def test_quota_during_selection_verification_stops_without_navigation(self):
        self.replies[:] = [
            (200, response([{"text": json.dumps(question())}])),
            (429, {"error": {"message": "quota"}}),
        ]
        desktop = QuizDesktop()
        runner = QuestionRunner(
            desktop, Vision(self.client()), sleep=lambda _: None, progress=lambda _: None
        )
        with self.assertRaises(ApiError):
            runner.run(2)
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(desktop.clicks, [(100, 200)])
        self.assertEqual(runner.answered, 0)
