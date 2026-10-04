"""Gemini requests, complete-answer parsing, and bounded HTTP transport."""

import base64
import json
import subprocess
import tempfile
from pathlib import Path

from .config import Config
from .errors import AcademicError, ApiError
from .images import png_size

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
REQUEST_LIMIT = 20_000_000
RESPONSE_LIMIT = 4_194_304
ANSWER_PROMPT = """Analyze the problem shown in the image and return ONLY the final answer(s).
Do not include steps, headings, reasoning, conversational text, Markdown, or LaTeX.
For multiple choice with letters, return the correct letter(s), e.g. A & C.
For multiple choice without letters, return Option 1, Option 2, etc., top to bottom.
Use standard Unicode math symbols for mathematical answers.
If the problem is incomplete or unreadable, return: Cannot read problem reliably."""


class CurlTransport:
    def __init__(self, endpoint: str = ENDPOINT):
        self.endpoint = endpoint

    def post(self, model: str, key: str, payload: bytes) -> dict:
        with tempfile.TemporaryDirectory(prefix="academic-http-") as directory:
            request = Path(directory) / "request.json"
            response = Path(directory) / "response.json"
            request.write_bytes(payload)
            args = [
                "curl",
                "--disable",
                "--silent",
                "--show-error",
                "--config",
                "-",
                "--connect-timeout",
                "10",
                "--max-time",
                "120",
                "--max-filesize",
                str(RESPONSE_LIMIT),
                "--header",
                "Content-Type: application/json",
                "--data-binary",
                f"@{request}",
                "--output",
                str(response),
                "--write-out",
                "%{http_code}",
                f"{self.endpoint}/{model}:generateContent",
            ]
            try:
                result = subprocess.run(
                    args,
                    input=f'header = "x-goog-api-key: {key}"\n'.encode(),
                    capture_output=True,
                    timeout=125,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                raise ApiError("Request timed out.") from None
            except OSError:
                raise ApiError("Cannot run curl; install it before solving.") from None
            if result.returncode:
                message = (
                    "Request timed out."
                    if result.returncode == 28
                    else f"Network request failed (curl {result.returncode})."
                )
                raise ApiError(message)
            try:
                code = int(result.stdout.decode("ascii").strip())
                if not 100 <= code <= 599:
                    raise ValueError
            except (ValueError, UnicodeError):
                raise ApiError("curl returned an invalid HTTP status.") from None
            try:
                if response.stat().st_size > RESPONSE_LIMIT:
                    raise ApiError("API response exceeded the size limit.")
                body = json.loads(response.read_bytes())
            except (OSError, ValueError, UnicodeError, RecursionError):
                if code != 200:
                    raise ApiError(f"HTTP {code}: API request failed.", code) from None
                raise ApiError("API returned an empty or malformed response.") from None
            if not isinstance(body, dict):
                raise ApiError("API returned a malformed response.", code)
            if code != 200:
                error = body.get("error")
                message = error.get("message") if isinstance(error, dict) else None
                message = message if isinstance(message, str) else "API request failed."
                message = message.strip()[:1000]
                raise ApiError(f"HTTP {code}: {message}", code)
            return body


def complete_text(body: dict) -> str:
    try:
        candidate = body["candidates"][0]
        if candidate.get("finishReason") != "STOP":
            raise ApiError(
                f"No complete answer received ({candidate.get('finishReason', 'unknown')})."
            )
        parts = candidate["content"]["parts"]
        if not isinstance(parts, list):
            raise TypeError
        if any(not isinstance(part, dict) for part in parts):
            raise TypeError
        text = "".join(
            part["text"]
            for part in parts
            if part.get("thought") is not True and isinstance(part.get("text"), str)
        ).strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        raise ApiError(
            "No complete answer received (blocked, empty, or malformed response)."
        ) from None
    if not text:
        raise ApiError("No complete answer received (empty response).")
    return text


class GeminiClient:
    def __init__(self, config: Config, transport=None):
        self.config = config
        self.transport = transport or CurlTransport()

    def generate(
        self, image: bytes, prompt: str = ANSWER_PROMPT, *, schema=None, strict: bool = False
    ) -> str:
        png_size(image)
        payload: dict[str, object] = {
            "contents": [
                {
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": base64.b64encode(image).decode("ascii"),
                            }
                        },
                        {"text": prompt},
                    ]
                }
            ]
        }
        if schema is not None:
            payload["generationConfig"] = {
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            }
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        if len(serialized) >= REQUEST_LIMIT:
            raise AcademicError("Screenshot is too large for the 20 MB inline request budget.")
        error = None
        for key in self.config.keys:
            try:
                body = self.transport.post(self.config.model, key, serialized)
            except ApiError as failure:
                message = str(failure)
                for secret in self.config.keys:
                    message = message.replace(secret, "[redacted]")
                error = ApiError(message, failure.status)
                if strict or (
                    failure.status is not None
                    and failure.status not in (401, 403, 429)
                    and not 500 <= failure.status < 600
                ):
                    raise error from None
                continue
            return complete_text(body)
        raise error or ApiError("No API keys configured.")
