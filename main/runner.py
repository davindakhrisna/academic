"""Question Runner: inspect, validate, select, verify, and advance."""

import time
from dataclasses import dataclass

from .errors import AcademicError


@dataclass(frozen=True)
class RunResult:
    answered: int
    requested: int
    reason: str

    @property
    def complete(self):
        return self.answered == self.requested


class QuestionRunner:
    def __init__(self, desktop, vision, *, check=lambda: None, sleep=time.sleep, progress=print):
        self.desktop = desktop
        self.vision = vision
        self.check = check
        self.sleep = sleep
        self.progress = progress
        self.answered = 0

    def _inspect(self):
        self.check()
        frame = self.desktop.capture()
        observation = self.vision.inspect(frame.image)
        self.check()
        return frame, observation

    def run(self, count: int, *, dry_run=False) -> RunResult:
        if type(count) is not int or not 1 <= count <= 10_000:
            raise AcademicError("Question count must be an integer between 1 and 10000.")
        self.answered = 0
        for remaining in range(5, 0, -1):
            self.check()
            self.progress(f"Focus your browser. Starting in {remaining}...")
            self.sleep(1)
        seen = set()
        while self.answered < count:
            frame, observation = self._inspect()
            if observation.status != "question":
                return RunResult(
                    self.answered, count, f"{observation.status}: {observation.reason}"
                )
            fingerprint = observation.fingerprint
            if observation.selected_ids:
                return RunResult(self.answered, count, "Question already has selected answers.")
            if fingerprint in seen:
                return RunResult(
                    self.answered, count, "Question repeated; navigation did not advance."
                )
            desired = observation.answer_ids
            if any(not option.enabled for option in observation.options if option.id in desired):
                raise AcademicError("A proposed answer control is disabled.")
            if dry_run:
                labels = [option.label for option in observation.options if option.id in desired]
                self.progress("Proposed selection: " + "; ".join(labels))
                return RunResult(0, count, "Dry run finished; no clicks sent.")
            expected = set()
            for answer_id in desired:
                self.check()
                if observation.fingerprint != fingerprint or observation.status != "question":
                    raise AcademicError("Question changed or became answered during selection.")
                if observation.selected_ids != expected:
                    raise AcademicError("Selection changed unexpectedly; runner stopped.")
                option = next(option for option in observation.options if option.id == answer_id)
                if not option.enabled:
                    raise AcademicError("An answer control became disabled.")
                self.desktop.click(frame, option.point, check=self.check)
                expected.add(answer_id)
                self.sleep(0.3)
                frame, observation = self._inspect()
                if (
                    observation.status not in ("question", "answered")
                    or observation.fingerprint != fingerprint
                ):
                    raise AcademicError(
                        "Cannot verify the same question after selecting an answer."
                    )
                if observation.selected_ids != expected:
                    raise AcademicError(
                        "Answer selection was not confirmed; no further clicks sent."
                    )
                if observation.answer_ids and set(observation.answer_ids) != set(desired):
                    raise AcademicError(
                        "AI changed its answer during verification; runner stopped."
                    )
            self.answered += 1
            seen.add(fingerprint)
            self.progress(f"Verified question {self.answered}/{count}.")
            if self.answered == count:
                return RunResult(self.answered, count, "Requested question count reached.")
            if observation.next is None or not observation.next.enabled:
                return RunResult(
                    self.answered, count, "No enabled Next question control is visible."
                )
            self.check()
            self.desktop.click(frame, observation.next.point, check=self.check)
            self.sleep(1)
        return RunResult(self.answered, count, "Requested question count reached.")
