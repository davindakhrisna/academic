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
from main.openrouter import CurlTransport, OpenRouterClient
from main.runner import QuestionRunner
from main.vision import Vision
from tests.support.helpers import QuizDesktop, png, question
from tests.support.openrouter import response


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
        self.endpoint = f"http://127.0.0.1:{self.server.server_port}/api/v1/chat/completions"
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.environment = patch.dict(
            os.environ,
            {"NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1", "CURL_HOME": self.temp.name},
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def client(self):
        return OpenRouterClient(
            Config("qwen/qwen3.8-27b:free", "primary"), CurlTransport(self.endpoint)
        )

    def test_real_post_single_key_native_model_fallback_and_png(self):
        self.replies[:] = [
            (
                200,
                {
                    **response("Option 2", reasoning="hidden"),
                    "model": "deepseek/deepseek-v4.1-flash",
                },
            )
        ]
        Path(self.temp.name, ".curlrc").write_text(f'url = "{self.endpoint}/unexpected"\n')
        self.assertEqual(self.client().generate(png()), "Option 2")
        self.assertEqual(len(self.requests), 1)
        path, headers, raw = self.requests[0]
        self.assertEqual(path, "/api/v1/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer primary")
        self.assertEqual(headers["Content-Type"], "application/json")
        payload = json.loads(raw)
        self.assertEqual(
            payload["models"], ["qwen/qwen3.8-27b:free", "deepseek/deepseek-v4.1-flash"]
        )
        image = payload["messages"][0]["content"][1]["image_url"]["url"]
        self.assertEqual(image.split(",", 1)[0], "data:image/png;base64")
        self.assertEqual(base64.b64decode(image.split(",", 1)[1]), png())

    def test_router_errors_after_model_fallback_stop_without_key_rotation(self):
        for code in (400, 401, 402, 429, 503):
            self.replies[:] = [(code, {"error": {"message": "models failed primary"}})]
            self.requests.clear()
            with self.subTest(code=code), self.assertRaises(ApiError) as caught:
                Vision(self.client()).inspect(png())
            self.assertEqual(caught.exception.status, code)
            self.assertNotIn("primary", str(caught.exception))
            self.assertEqual(len(self.requests), 1)

    def test_http_200_error_preserves_status_and_redacts_key(self):
        self.replies[:] = [(200, {"error": {"code": 429, "message": "quota primary"}})]
        with self.assertRaises(ApiError) as caught:
            self.client().generate(png())
        self.assertEqual(caught.exception.status, 429)
        self.assertEqual(str(caught.exception), "HTTP 429: quota [redacted]")
        self.assertEqual(len(self.requests), 1)

    def test_malformed_response_stops_without_input(self):
        for code, body in ((404, b"not found"), (200, b"not JSON")):
            self.replies[:] = [(code, body)]
            self.requests.clear()
            desktop = QuizDesktop()
            runner = QuestionRunner(
                desktop, Vision(self.client()), sleep=lambda _: None, progress=lambda _: None
            )
            with self.subTest(code=code), self.assertRaises(ApiError):
                runner.run(1)
            self.assertEqual(len(self.requests), 1)
            self.assertEqual(desktop.clicks, [])

    def test_full_question_runner_with_real_http_and_structured_vision(self):
        states = [
            question(1),
            question(2, mode="multi", answers=("1", "3")),
        ]
        self.replies[:] = [(200, response(json.dumps(state))) for state in states]
        desktop = QuizDesktop(states)
        result = QuestionRunner(
            desktop, Vision(self.client()), sleep=lambda _: None, progress=lambda _: None
        ).run(2)
        self.assertTrue(result.complete)
        self.assertEqual(desktop.clicks, [(100, 200), (900, 900), (100, 100), (100, 300)])
        self.assertEqual(len(self.requests), 2)
        for _, headers, raw in self.requests:
            payload = json.loads(raw)
            self.assertEqual(headers["Authorization"], "Bearer primary")
            self.assertEqual(payload["response_format"]["type"], "json_schema")
            self.assertEqual(
                payload["models"], ["qwen/qwen3.8-27b:free", "deepseek/deepseek-v4.1-flash"]
            )
            self.assertIn(
                "options", payload["response_format"]["json_schema"]["schema"]["properties"]
            )

    def test_quota_on_next_question_stops_before_answering_it(self):
        self.replies[:] = [
            (200, response(json.dumps(question()))),
        ] + [(429, {"error": {"message": "quota"}})]
        desktop = QuizDesktop([question(1), question(2)])
        runner = QuestionRunner(
            desktop, Vision(self.client()), sleep=lambda _: None, progress=lambda _: None
        )
        with self.assertRaises(ApiError):
            runner.run(2)
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(desktop.clicks, [(100, 200), (900, 900)])
        self.assertEqual(runner.answered, 1)
