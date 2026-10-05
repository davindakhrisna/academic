import unittest

from main.errors import AcademicError, ApiError, Cancelled
from main.runner import QuestionRunner
from tests.support.helpers import QuizDesktop, QuizVision, question, stop_screen


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

    def test_multi_selection_uses_one_api_call(self):
        desktop = QuizDesktop([question(mode="multi", answers=("1", "3"))])
        runner, _, vision, _, _ = self.runner(desktop)
        self.assertTrue(runner.run(1).complete)
        self.assertEqual(desktop.clicks, [(100, 100), (100, 300)])
        self.assertEqual(vision.calls, 1)

    def test_loop_navigation_and_limit(self):
        desktop = QuizDesktop(
            [question(1), question(2, mode="multi", answers=("1", "3")), question(3)]
        )
        runner, _, vision, _, _ = self.runner(desktop)
        result = runner.run(2)
        self.assertEqual(result.answered, 2)
        self.assertEqual(desktop.index, 1)
        self.assertEqual(desktop.clicks, [(100, 200), (900, 900), (100, 100), (100, 300)])
        self.assertEqual(vision.calls, 2)

    def test_non_question_and_completed_screens_send_no_input(self):
        for status in ("not_question", "complete"):
            desktop = QuizDesktop([stop_screen(status)])
            with self.subTest(status=status):
                result = self.runner(desktop)[0].run(3)
                self.assertEqual(result.answered, 0)
                self.assertEqual(desktop.clicks, [])

    def test_ambiguous_screen_warns_and_continues(self):
        runner, desktop, vision, _, messages = self.runner(QuizDesktop([stop_screen("ambiguous")]))
        vision.after_inspect = lambda: desktop.questions.__setitem__(0, question())
        self.assertTrue(runner.run(1).complete)
        self.assertEqual(vision.calls, 2)
        self.assertTrue(any("Warning: ambiguous" in message for message in messages))

    def test_already_selected_question_continues_without_toggling(self):
        desktop = QuizDesktop([question(selected=("2",))])
        result = self.runner(desktop)[0].run(1)
        self.assertTrue(result.complete)
        self.assertFalse(desktop.clicks)

    def test_already_graded_question_continues(self):
        data = question(selected=("2",))
        data["status"] = "answered"
        desktop = QuizDesktop([data])
        result = self.runner(desktop)[0].run(1)
        self.assertTrue(result.complete)
        self.assertFalse(desktop.clicks)

    def test_quota_and_other_errors_send_no_input(self):
        for error in (ApiError("quota", 429), ApiError("timeout"), AcademicError("malformed JSON")):
            runner, desktop, vision, _, _ = self.runner()
            vision.failure = error
            with self.subTest(error=error), self.assertRaises(AcademicError):
                runner.run(2)
            self.assertFalse(desktop.clicks)

    def test_stale_screenshot_warns_and_clicks_without_another_api_call(self):
        runner, desktop, vision, _, messages = self.runner()
        vision.after_inspect = lambda: setattr(desktop, "version", desktop.version + 1)
        self.assertTrue(runner.run(1).complete)
        self.assertEqual(desktop.clicks, [(100, 200)])
        self.assertEqual(vision.calls, 1)
        self.assertTrue(any("Warning: screen" in message for message in messages))

    def test_selection_is_not_rechecked_by_the_model_or_retried(self):
        runner, desktop, vision, _, _ = self.runner()
        desktop.ignore_clicks = True
        self.assertTrue(runner.run(1).complete)
        self.assertEqual(desktop.clicks, [(100, 200)])
        self.assertEqual(vision.calls, 1)

    def test_local_focus_change_after_answer_continues_to_next(self):
        runner, desktop, _, _, _ = self.runner(QuizDesktop([question(1), question(2)]))

        def sleep(seconds):
            if seconds == 0.3:
                desktop.active = type(desktop.active)("other", desktop.active.bounds, "Other")

        runner.sleep = sleep
        self.assertTrue(runner.run(2).complete)
        self.assertEqual(desktop.clicks, [(100, 200), (900, 900), (100, 200)])

    def test_window_moves_and_changes_during_analysis_warn_and_continue(self):
        runner, desktop, vision, _, messages = self.runner()
        vision.after_inspect = lambda: setattr(
            desktop, "active", type(desktop.active)("other", (100, 100, 1100, 1100), "Other")
        )
        self.assertTrue(runner.run(1).complete)
        self.assertEqual(desktop.clicks, [(200, 300)])
        self.assertTrue(any("Warning: screen" in message for message in messages))

    def test_cancellation_after_answer_stops_before_next(self):
        runner, desktop, _, _, _ = self.runner()

        def cancelled():
            raise Cancelled()

        def sleep(seconds):
            if seconds == 0.3:
                runner.check = cancelled

        runner.sleep = sleep
        with self.assertRaises(Cancelled):
            runner.run(2)
        self.assertEqual(desktop.clicks, [(100, 200)])
        self.assertEqual(runner.answered, 0)

    def test_missing_next_warns_until_a_non_question_screen(self):
        data = question()
        data["next"] = None
        runner, desktop, _, _, messages = self.runner(QuizDesktop([data]))

        def sleep(seconds):
            if runner.answered:
                desktop.questions[0] = stop_screen()

        runner.sleep = sleep
        result = runner.run(2)
        self.assertEqual(result.answered, 1)
        self.assertIn("not_question", result.reason)
        self.assertTrue(any("Warning: no enabled Next" in message for message in messages))
        self.assertEqual(desktop.clicks, [(100, 200)])

    def test_repeated_question_is_not_answered_twice(self):
        runner, desktop, _, _, messages = self.runner(
            QuizDesktop([question(), question(), question(3)])
        )
        result = runner.run(2)
        self.assertEqual(result.answered, 2)
        self.assertTrue(any("Warning: question repeated" in message for message in messages))
        self.assertEqual(desktop.clicks, [(100, 200), (900, 900), (900, 900), (100, 200)])

    def test_disabled_proposed_control_sends_no_input(self):
        data = question()
        data["options"][1]["enabled"] = False
        runner, desktop, vision, _, messages = self.runner(QuizDesktop([data]))
        vision.after_inspect = lambda: desktop.questions.__setitem__(0, stop_screen())
        self.assertEqual(runner.run(1).answered, 0)
        self.assertTrue(
            any("Warning: proposed answer is disabled" in message for message in messages)
        )
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
