import copy
import json
import struct
import zlib

from main.desktop import Desktop, Window
from main.vision import parse_observation


def png(marker=0, width=8, height=8):
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    pixels = (
        b"\x00" + bytes((marker & 255, (marker >> 8) & 255, (marker >> 16) & 255)) * width
    ) * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )


def question(number=1, mode="single", answers=("2",), selected=()):
    return {
        "status": "question",
        "reason": "",
        "question": f"Question {number}: choose the correct answer.",
        "selection_mode": mode,
        "options": [
            {
                "id": str(index),
                "label": f"Option {index}",
                "point": {"x": 100, "y": index * 100},
                "selected": str(index) in selected,
                "enabled": True,
            }
            for index in range(1, 4)
        ],
        "answer_ids": list(answers),
        "next": {
            "label": "Next",
            "point": {"x": 900, "y": 900},
            "action": "next_question",
            "enabled": True,
        },
    }


def stop_screen(status="not_question"):
    return {
        "status": status,
        "reason": "Not an unanswered selectable question.",
        "question": "",
        "selection_mode": "none",
        "options": [],
        "answer_ids": [],
        "next": None,
    }


class QuizDesktop(Desktop):
    """A deterministic quiz exercising the real screenshot guard and runner."""

    def __init__(self, questions=None):
        super().__init__()
        self.questions = copy.deepcopy(questions or [question()])
        self.index = 0
        self.images = {}
        self.clicks = []
        self.active = Window("browser", (0, 0, 1000, 1000), "Practice quiz")
        self.ignore_clicks = False
        self.wrong_selection = False
        self.after_capture = None
        self.version = 0

    @property
    def state(self):
        return self.questions[self.index]

    def window(self):
        return self.active

    def grab(self, bounds):
        serialized = json.dumps(self.state, sort_keys=True) + str(self.version)
        for image, (signature, _) in self.images.items():
            if signature == serialized:
                return image
        image = png(len(self.images))
        self.images[image] = (serialized, copy.deepcopy(self.state))
        if self.after_capture:
            self.after_capture()
        return image

    def send_click(self, window, position, *, check=lambda: None):
        check()
        self.clicks.append(position)
        if self.ignore_clicks:
            return
        if position == (900, 900):
            if self.index + 1 < len(self.questions):
                self.index += 1
            return
        option_id = str(position[1] // 100)
        if self.wrong_selection:
            option_id = "1"
        for option in self.state["options"]:
            if self.state["selection_mode"] == "single":
                option["selected"] = option["id"] == option_id
            elif option["id"] == option_id:
                option["selected"] = not option["selected"]


class QuizVision:
    def __init__(self, desktop):
        self.desktop = desktop
        self.calls = 0
        self.failure = None
        self.after_inspect = None

    def inspect(self, image):
        self.calls += 1
        if self.failure:
            raise self.failure
        result = parse_observation(json.dumps(self.desktop.images[image][1]))
        if self.after_inspect:
            self.after_inspect()
        return result
