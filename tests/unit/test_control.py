import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main.control import RunControl, request_stop
from main.errors import AcademicError, Cancelled


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def test_stop_request_is_detected(self):
        with RunControl(self.directory) as control:
            control.check()
            request_stop(self.directory)
            with self.assertRaises(Cancelled):
                control.check()

    def test_stale_stop_is_cleared_on_a_new_run(self):
        request_stop(self.directory)
        with RunControl(self.directory) as control:
            control.check()

    def test_second_runner_cannot_acquire_lock(self):
        with (
            RunControl(self.directory),
            self.assertRaisesRegex(AcademicError, "already running"),
            RunControl(self.directory),
        ):
            self.fail("second runner acquired lock")
        with RunControl(self.directory):
            pass

    def test_lock_is_released_after_failure(self):
        with self.assertRaises(ValueError), RunControl(self.directory):
            raise ValueError()
        with RunControl(self.directory):
            pass

    def test_lock_closes_when_resetting_stop_file_fails(self):
        control = RunControl(self.directory)
        with patch("main.control.Path.unlink", side_effect=OSError), self.assertRaises(OSError):
            control.__enter__()
        self.assertIsNone(control.lock)
        with RunControl(self.directory):
            pass
