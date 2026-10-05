"""Question Runner: inspect once per question, select, and advance."""

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
        self.desktop.guarded = False
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
            if observation.status in ("not_question", "complete"):
                return RunResult(
                    self.answered, count, f"{observation.status}: {observation.reason}"
                )
            fingerprint = observation.fingerprint
            if observation.status == "ambiguous":
                self.progress(
                    f"Warning: ambiguous screenshot: {observation.reason}; inspecting again."
                )
                self.sleep(1)
                continue
            desired = observation.answer_ids
            if dry_run:
                labels = [option.label for option in observation.options if option.id in desired]
                self.progress("Proposed selection: " + "; ".join(labels))
                return RunResult(0, count, "Dry run finished; no clicks sent.")
            if fingerprint not in seen:
                options = [option for option in observation.options if option.id in desired]
                if any(not option.enabled and not option.selected for option in options):
                    self.progress("Warning: proposed answer is disabled; inspecting again.")
                    self.sleep(1)
                    continue
                for option in options:
                    if option.selected:
                        continue
                    self.check()
                    self.desktop.click(frame, option.point, check=self.check, warning=self.progress)
                    self.sleep(0.3)
                    self.check()
                    frame = self.desktop.capture()
                    self.check()
                self.answered += 1
                seen.add(fingerprint)
                self.progress(f"Answered question {self.answered}/{count}.")
            else:
                self.progress(
                    "Warning: question repeated; continuing navigation without selecting again."
                )
            if self.answered == count:
                return RunResult(self.answered, count, "Requested question count reached.")
            if observation.next is None or not observation.next.enabled:
                self.progress(
                    "Warning: no enabled Next question control is visible; inspecting again."
                )
                self.sleep(1)
                continue
            self.check()
            self.desktop.click(
                frame, observation.next.point, check=self.check, warning=self.progress
            )
            self.sleep(1)
        return RunResult(self.answered, count, "Requested question count reached.")
