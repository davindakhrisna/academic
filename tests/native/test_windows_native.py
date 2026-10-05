"""Opt-in proof of real Windows screenshot/input against a local practice UI."""

import ctypes
import json
import os
import sys
import time
import unittest

from academia.images import png_size
from academia.runner import QuestionRunner
from academia.vision import parse_observation
from academia.windows import Input, WindowsAPI, WindowsDesktop


@unittest.skipUnless(sys.platform == "win32", "native Windows ABI test requires Windows")
class WindowsABITests(unittest.TestCase):
    def test_sendinput_structure_size(self):
        self.assertEqual(ctypes.sizeof(Input), 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)


@unittest.skipUnless(
    sys.platform == "win32" and os.environ.get("ACADEMIC_WINDOWS_GUI_TESTS") == "1",
    "requires Windows interactive desktop and ACADEMIC_WINDOWS_GUI_TESTS=1",
)
class WindowsNativeTests(unittest.TestCase):
    def test_real_capture_single_multi_click_and_navigation(self):
        import tkinter as tk

        api = WindowsAPI()  # Select physical DPI coordinates before creating the fixture.
        root = tk.Tk()
        self.addCleanup(root.destroy)
        root.title("Academic local test fixture")
        root.geometry("640x460+100+100")
        state = {"number": 1, "widgets": [], "values": [], "next": None}

        def build(number):
            for widget in root.winfo_children():
                widget.destroy()
            state["number"] = number
            tk.Label(root, text=f"Practice question {number}").pack(pady=20)
            state["widgets"] = []
            state["values"] = []
            single = tk.IntVar(value=0)
            for index in range(1, 4):
                if number == 1:
                    widget = tk.Radiobutton(
                        root, text=f"Option {index}", variable=single, value=index
                    )
                    value = single
                else:
                    value = tk.BooleanVar(value=False)
                    widget = tk.Checkbutton(root, text=f"Option {index}", variable=value)
                widget.pack(pady=12)
                state["widgets"].append(widget)
                state["values"].append(value)
            button = tk.Button(root, text="Next", command=lambda: build(2))
            button.pack(pady=20)
            state["next"] = button
            root.update()

        build(1)
        root.lift()
        root.focus_force()
        root.update()
        desktop = WindowsDesktop(api=api, browsers={"python.exe", "pythonw.exe"})
        initial_window = desktop.window()

        def point(widget, window):
            left, top, right, bottom = window.bounds
            return {
                "x": 1000
                * (widget.winfo_rootx() + widget.winfo_width() / 2 - left)
                / (right - left),
                "y": 1000
                * (widget.winfo_rooty() + widget.winfo_height() / 2 - top)
                / (bottom - top),
            }

        class FixtureVision:
            def inspect(self, image):
                # The AI is substituted; native screenshot capture and mouse input are real.
                window = desktop.window()
                left, top, right, bottom = window.bounds
                if png_size(image) != (right - left, bottom - top):
                    raise AssertionError("Screenshot/DPI coordinates disagree")
                number = state["number"]
                data = {
                    "status": "question",
                    "reason": "",
                    "question": f"Practice question {number}",
                    "selection_mode": "single" if number == 1 else "multi",
                    "options": [],
                    "answer_ids": ["2"] if number == 1 else ["1", "3"],
                    "next": {
                        "label": "Next",
                        "point": point(state["next"], window),
                        "action": "next_question",
                        "enabled": True,
                    },
                }
                for index, widget in enumerate(state["widgets"], 1):
                    value = state["values"][index - 1].get()
                    selected = value == index if number == 1 else bool(value)
                    data["options"].append(
                        {
                            "id": str(index),
                            "label": f"Option {index}",
                            "point": point(widget, window),
                            "selected": selected,
                            "enabled": True,
                        }
                    )
                return parse_observation(json.dumps(data))

        def pump(_seconds):
            time.sleep(0.1)
            root.update()
            time.sleep(0.05)  # Allow the desktop compositor to present the painted frame.
            root.update()

        result = QuestionRunner(desktop, FixtureVision(), sleep=pump, progress=lambda _: None).run(
            2
        )
        self.assertEqual(result.answered, 2)
        self.assertEqual(state["number"], 2)
        self.assertEqual([value.get() for value in state["values"]], [True, False, True])
        self.assertEqual(desktop.window().identity, initial_window.identity)
