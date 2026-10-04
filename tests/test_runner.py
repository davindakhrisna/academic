import unittest
from dataclasses import replace

from main.errors import AcademicError, ApiError, Cancelled
from main.runner import QuestionRunner
from tests.helpers import QuizDesktop, QuizVision, question, stop_screen


class RunnerTests(unittest.TestCase):
    def runner(self, desktop=None, check=lambda: None):
        desktop = desktop or QuizDesktop()
        vision = QuizVision(desktop)
        sleeps, messages = [], []
        runner = QuestionRunner(
            desktop, vision, check=check, sleep=sleeps.append, progress=messages.append
        )
        return runner, desktop, vision, sleeps, messages

    def test_countdown_is_five_seconds_before_capture(self):
        runner, desktop, _, sleeps, messages = self.runner()

        def sleep(seconds):
            if len(sleeps) < 5:
                self.assertFalse(desktop.images)
                self.assertFalse(desktop.clicks)
            sleeps.append(seconds)

        runner.sleep = sleep
        runner.run(1)
        self.assertEqual(sleeps[:5], [1] * 5)
        self.assertEqual(len([message for message in messages if "Starting" in message]), 5)

    def test_single_selection_and_count_endpoint_no_next_click(self):
        runner, desktop, _, _, _ = self.runner()
        result = runner.run(1)
        self.assertTrue(result.complete)
        self.assertEqual(desktop.clicks, [(100, 200)])
        self.assertTrue(desktop.state["options"][1]["selected"])

    def test_multi_selection_is_verified_one_control_at_a_time(self):
        desktop = QuizDesktop([question(mode="multi", answers=("1", "3"))])
        runner, _, vision, _, _ = self.runner(desktop)
        self.assertTrue(runner.run(1).complete)
        self.assertEqual(desktop.clicks, [(100, 100), (100, 300)])
        self.assertEqual(vision.calls, 3)

    def test_loop_navigation_and_limit(self):
        desktop = QuizDesktop(
            [question(1), question(2, mode="multi", answers=("1", "3")), question(3)]
        )
        runner, _, _, _, _ = self.runner(desktop)
        result = runner.run(2)
        self.assertEqual(result.answered, 2)
        self.assertEqual(desktop.index, 1)
        self.assertEqual(desktop.clicks, [(100, 200), (900, 900), (100, 100), (100, 300)])

    def test_non_question_ambiguous_and_completed_screens_send_no_input(self):
        for status in ("not_question", "ambiguous", "complete"):
            desktop = QuizDesktop([stop_screen(status)])
            with self.subTest(status=status):
                result = self.runner(desktop)[0].run(3)
                self.assertEqual(result.answered, 0)
                self.assertEqual(desktop.clicks, [])

    def test_already_selected_question_stops_without_toggling(self):
        desktop = QuizDesktop([question(selected=("2",))])
        result = self.runner(desktop)[0].run(1)
        self.assertIn("already", result.reason)
        self.assertFalse(desktop.clicks)

    def test_already_graded_question_stops(self):
        data = question()
        data["status"] = "answered"
        desktop = QuizDesktop([data])
        result = self.runner(desktop)[0].run(1)
        self.assertIn("answered", result.reason)
        self.assertFalse(desktop.clicks)

    def test_quota_and_other_errors_send_no_input(self):
        for error in (ApiError("quota", 429), ApiError("timeout"), AcademicError("malformed JSON")):
            runner, desktop, vision, _, _ = self.runner()
            vision.failure = error
            with self.subTest(error=error), self.assertRaises(AcademicError):
                runner.run(2)
            self.assertFalse(desktop.clicks)

    def test_stale_screenshot_does_not_click(self):
        runner, desktop, vision, _, _ = self.runner()
        vision.after_inspect = lambda: setattr(desktop, "version", desktop.version + 1)
        with self.assertRaisesRegex(AcademicError, "changed after analysis"):
            runner.run(1)
        self.assertFalse(desktop.clicks)

    def test_failed_click_is_not_retried_or_counted(self):
        runner, desktop, _, _, _ = self.runner()
        desktop.ignore_clicks = True
        with self.assertRaisesRegex(AcademicError, "not confirmed"):
            runner.run(1)
        self.assertEqual(desktop.clicks, [(100, 200)])
        self.assertEqual(runner.answered, 0)

    def test_wrong_selection_stops_without_next(self):
        runner, desktop, _, _, _ = self.runner()
        desktop.wrong_selection = True
        with self.assertRaisesRegex(AcademicError, "not confirmed"):
            runner.run(2)
        self.assertEqual(desktop.clicks, [(100, 200)])

    def test_changed_ai_answer_stops_without_navigation(self):
        runner, desktop, _, _, _ = self.runner()

        class InconsistentVision(QuizVision):
            def inspect(self, image):
                observation = super().inspect(image)
                return replace(observation, answer_ids=("1",)) if self.calls > 1 else observation

        runner.vision = InconsistentVision(desktop)
        with self.assertRaisesRegex(AcademicError, "changed its answer"):
            runner.run(2)
        self.assertEqual(desktop.clicks, [(100, 200)])
        self.assertEqual(runner.answered, 0)

    def test_missing_next_stops_after_verified_answer(self):
        data = question()
        data["next"] = None
        runner, desktop, _, _, _ = self.runner(QuizDesktop([data]))
        result = runner.run(2)
        self.assertEqual(result.answered, 1)
        self.assertIn("Next", result.reason)
        self.assertEqual(desktop.clicks, [(100, 200)])

    def test_repeated_question_is_not_answered_twice(self):
        runner, desktop, _, _, _ = self.runner(QuizDesktop([question(), question()]))
        result = runner.run(2)
        self.assertEqual(result.answered, 1)
        self.assertIn("repeated", result.reason)
        self.assertEqual(desktop.clicks, [(100, 200), (900, 900)])

    def test_disabled_proposed_control_sends_no_input(self):
        data = question()
        data["options"][1]["enabled"] = False
        runner, desktop, _, _, _ = self.runner(QuizDesktop([data]))
        with self.assertRaisesRegex(AcademicError, "disabled"):
            runner.run(1)
        self.assertFalse(desktop.clicks)

    def test_dry_run_proposes_answers_without_input(self):
        runner, desktop, _, _, messages = self.runner()
        result = runner.run(2, dry_run=True)
        self.assertEqual(result.answered, 0)
        self.assertFalse(desktop.clicks)
        self.assertTrue(any("Proposed selection" in message for message in messages))

    def test_user_cancellation_during_countdown_and_after_api(self):
        def cancelled():
            raise Cancelled()

        runner, desktop, _, sleeps, _ = self.runner(check=cancelled)
        with self.assertRaises(Cancelled):
            runner.run(1)
        self.assertFalse(sleeps)
        self.assertFalse(desktop.clicks)
        runner, desktop, vision, _, _ = self.runner()
        vision.after_inspect = lambda: setattr(runner, "check", cancelled)
        with self.assertRaises(Cancelled):
            runner.run(1)
        self.assertFalse(desktop.clicks)

    def test_cancellation_during_guard_capture_sends_no_click(self):
        runner, desktop, vision, _, _ = self.runner()
        cancelled = [False]

        def check():
            if cancelled[0]:
                raise Cancelled()

        runner.check = check

        # Force a new frame during the guard capture, and cancel while it is read.
        def after_inspect():
            desktop.after_capture = lambda: cancelled.__setitem__(0, True)
            desktop.version += 1

        vision.after_inspect = after_inspect
        with self.assertRaises(Cancelled):
            runner.run(1)
        self.assertFalse(desktop.clicks)

    def test_invalid_count_does_not_capture(self):
        for count in (0, -1, 10_001, True, 1.2):
            runner, desktop, _, _, _ = self.runner()
            with self.subTest(count=count), self.assertRaises(AcademicError):
                runner.run(count)
            self.assertFalse(desktop.images)
