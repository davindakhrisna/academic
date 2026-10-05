import json
import unittest

from academia.errors import AcademicError
from academia.vision import Vision, parse_observation
from tests.support.helpers import png, question, stop_screen


class VisionTests(unittest.TestCase):
    def test_single_and_multi_selection(self):
        single = parse_observation(json.dumps(question()))
        multi = parse_observation(json.dumps(question(mode="multi", answers=("1", "3"))))
        self.assertEqual(single.answer_ids, ("2",))
        self.assertEqual(multi.answer_ids, ("1", "3"))

    def test_non_question_statuses_have_no_actions(self):
        for status in ("not_question", "ambiguous", "complete"):
            with self.subTest(status=status):
                observation = parse_observation(json.dumps(stop_screen(status)))
                self.assertFalse(observation.options)
                self.assertIsNone(observation.next)

    def test_unsafe_and_malformed_actions_are_rejected(self):
        changes = [
            lambda data: data.update(extra="arbitrary command"),
            lambda data: data.update(status="click_anywhere"),
            lambda data: data.update(selection_mode="text"),
            lambda data: data.update(answer_ids=[]),
            lambda data: data.update(answer_ids=["1", "2"]),
            lambda data: data.update(answer_ids=["2", "2"]),
            lambda data: data.update(answer_ids=["unknown"]),
            lambda data: data["options"][0].update(id="2"),
            lambda data: data["options"][0].update(selected="false"),
            lambda data: data["options"][0].update(enabled=1),
            lambda data: data["options"][0]["point"].update(x=True),
            lambda data: data["options"][0]["point"].update(y=1000),
            lambda data: data["options"][0]["point"].update(x=-1),
            lambda data: data["options"][0]["point"].update(x=float("nan")),
            lambda data: data["options"][0]["point"].update(x=float("inf")),
            lambda data: data["options"][1].update(point=dict(data["options"][0]["point"])),
            lambda data: data["next"].update(point=dict(data["options"][0]["point"])),
            lambda data: data["next"].update(action="submit"),
            lambda data: data["next"].update(label="Finish and submit"),
            lambda data: data.update(question=""),
            lambda data: data.update(options=[]),
        ]
        for index, change in enumerate(changes):
            data = question()
            change(data)
            with self.subTest(case=index), self.assertRaises(AcademicError):
                parse_observation(json.dumps(data))

    def test_non_question_cannot_smuggle_actions(self):
        data = stop_screen()
        data["next"] = question()["next"]
        with self.assertRaises(AcademicError):
            parse_observation(json.dumps(data))

    def test_bad_coordinates_identify_the_control_axis_and_value(self):
        data = question()
        data["options"][1]["point"]["x"] = 1250
        with self.assertRaisesRegex(AcademicError, "option 2: x=1250"):
            parse_observation(json.dumps(data))
        data = question()
        data["next"]["point"]["y"] = 0
        with self.assertRaisesRegex(AcademicError, "Next button: y=0"):
            parse_observation(json.dumps(data))

    def test_duplicate_json_fields_and_non_json_fail(self):
        for text in (
            '{"status":"question","status":"complete"}',
            "```json\n{}\n```",
            "null",
            "[1]",
        ):
            with self.subTest(text=text), self.assertRaises(AcademicError):
                parse_observation(text)

    def test_fingerprint_ignores_selected_state_and_coordinates_but_not_question(self):
        data = question()
        before = parse_observation(json.dumps(data))
        data["options"][1]["selected"] = True
        data["options"][0]["point"]["x"] = 120
        changed = parse_observation(json.dumps(data))
        self.assertEqual(before.fingerprint, changed.fingerprint)
        data["question"] = "A different question"
        self.assertNotEqual(before.fingerprint, parse_observation(json.dumps(data)).fingerprint)

    def test_visual_inspection_requests_structured_output(self):
        class Client:
            def generate(self, image, prompt, **settings):
                self.prompt = prompt
                self.calls = getattr(self, "calls", 0) + 1
                self.settings = settings
                return json.dumps(question())

        client = Client()
        Vision(client).inspect(png(width=1920, height=1080))
        self.assertIn("schema", client.settings)
        self.assertIn("1920 × 1080 pixels", client.prompt)
        self.assertIn("1000 * pixel_x / screenshot_width", client.prompt)
        self.assertEqual(client.calls, 1)
