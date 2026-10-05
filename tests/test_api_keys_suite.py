import json
import unittest

from main.errors import AcademicError, ApiError
from tests.live_api_keys import probe
from tests.helpers import question, stop_screen
from tests.test_gemini import Transport, response


class ApiKeySuiteTests(unittest.TestCase):
    def setUp(self):
        self.values = {
            "GOOGLE_API_KEY": "primary-secret",
            "GOOGLE_API_KEY_BACKUP": "backup-secret",
            "GOOGLE_API_KEY_TERTIARY": "tertiary-secret",
            "GEMINI_MODEL": "test-model",
        }

    def test_each_slot_uses_only_its_own_key_and_model(self):
        for index, key in enumerate(("primary-secret", "backup-secret", "tertiary-secret")):
            with self.subTest(slot=index):
                transport = Transport([response([{"text": "RED"}])])
                probe(index, self.values, transport)
                self.assertEqual(len(transport.calls), 1)
                self.assertEqual(transport.calls[0][:2], ("test-model", key))
                self.assertIn(b'"mimeType":"image/png"', transport.calls[0][2])

    def test_runner_probe_uses_structured_request_and_validates_non_question(self):
        transport = Transport([response([{"text": json.dumps(stop_screen())}])])
        probe(0, self.values, transport, runner=True)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(transport.calls[0][:2], ("test-model", "primary-secret"))
        payload = json.loads(transport.calls[0][2])
        self.assertIn("responseJsonSchema", payload["generationConfig"])
        for data in (question(), {**stop_screen(), "next": question()["next"]}):
            transport = Transport([response([{"text": json.dumps(data)}])])
            with self.subTest(data=data), self.assertRaises(AcademicError):
                probe(0, self.values, transport, runner=True)
            self.assertEqual(len(transport.calls), 1)

    def test_quota_failure_never_falls_back_and_redacts_all_keys(self):
        transport = Transport([ApiError("primary-secret backup-secret tertiary-secret", 429)])
        with self.assertRaises(AcademicError) as caught:
            probe(0, self.values, transport)
        self.assertEqual(str(caught.exception), "[redacted] [redacted] [redacted]")
        self.assertEqual(len(transport.calls), 1)

    def test_dotted_key_is_sent_unchanged(self):
        self.values["GOOGLE_API_KEY_BACKUP"] = "AQ.synthetic_key-with.dot"
        transport = Transport([response([{"text": "RED"}])])
        probe(1, self.values, transport)
        self.assertEqual(transport.calls[0][1], "AQ.synthetic_key-with.dot")

    def test_empty_backup_does_not_shift_tertiary_into_its_slot(self):
        self.values["GOOGLE_API_KEY_BACKUP"] = ""
        transport = Transport([response([{"text": "RED"}])])
        with self.assertRaisesRegex(AcademicError, "GOOGLE_API_KEY_BACKUP"):
            probe(1, self.values, transport)
        self.assertEqual(transport.calls, [])
        probe(2, self.values, transport)
        self.assertEqual(transport.calls[0][1], "tertiary-secret")

    def test_wrong_vision_answer_fails_without_printing_response(self):
        transport = Transport([response([{"text": "primary-secret"}])])
        with self.assertRaisesRegex(AcademicError, "Vision response") as caught:
            probe(0, self.values, transport)
        self.assertNotIn("primary-secret", str(caught.exception))

    def test_placeholder_and_unsafe_keys_do_not_make_requests(self):
        for key in ("your_primary_key", 'unsafe"key'):
            with self.subTest(key=key):
                self.values["GOOGLE_API_KEY"] = key
                transport = Transport([])
                with self.assertRaises(AcademicError):
                    probe(0, self.values, transport)
                self.assertEqual(transport.calls, [])
