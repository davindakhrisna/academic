"""Synthetic chat completion responses and an in-memory transport."""

import json


def response(content="A", reason="stop", reasoning=None):
    return {
        "choices": [
            {
                "finish_reason": reason,
                "message": {"role": "assistant", "content": content, "reasoning": reasoning},
            }
        ]
    }


class Transport:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def post(self, key, payload):
        self.calls.append((json.loads(payload)["model"], key, payload))
        result = self.replies.pop(0)
        if isinstance(result, Exception):
            raise result
        return result
