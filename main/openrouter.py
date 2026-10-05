"""OpenRouter vision requests, complete-answer parsing, and bounded HTTP transport."""

import base64
import json
import subprocess
import tempfile
from pathlib import Path

from .config import Config
from .errors import AcademicError, ApiError
from .images import png_size
from .system import external_environment

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
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

    def post(self, key: str, payload: bytes) -> dict:
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
                self.endpoint,
            ]
            try:
                with external_environment() as environment:
                    result = subprocess.run(
                        args,
                        input=f'header = "Authorization: Bearer {key}"\n'.encode(),
                        capture_output=True,
                        timeout=125,
                        check=False,
                        env=environment,
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
            if code != 200 or "error" in body:
                error = body.get("error")
                message = error.get("message") if isinstance(error, dict) else None
                message = message if isinstance(message, str) else "API request failed."
                message = message.strip()[:1000]
                status = error.get("code") if isinstance(error, dict) else None
                if type(status) is not int or not 400 <= status <= 599:
                    status = code if code != 200 else None
                prefix = f"HTTP {status}" if status is not None else "API error"
                raise ApiError(f"{prefix}: {message}", status)
            return body


def complete_text(body: dict) -> str:
    try:
        candidate = body["choices"][0]
        if candidate.get("finish_reason") != "stop":
            raise ApiError(
                f"No complete answer received ({candidate.get('finish_reason', 'unknown')})."
            )
        message = candidate["message"]
        if message.get("refusal"):
            raise ApiError("API declined to answer the request.")
        text = message["content"]
        if not isinstance(text, str):
            raise TypeError
        text = text.strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        raise ApiError(
            "No complete answer received (blocked, empty, or malformed response)."
        ) from None
    if not text:
        raise ApiError("No complete answer received (empty response).")
    return text


class OpenRouterClient:
    def __init__(self, config: Config, transport=None):
        self.config = config
        self.transport = transport or CurlTransport()

    def generate(self, image: bytes, prompt: str = ANSWER_PROMPT, *, schema=None) -> str:
        png_size(image)
        models = [self.config.model]
        if self.config.fallback_model and self.config.fallback_model != self.config.model:
            models.append(self.config.fallback_model)
        payload: dict[str, object] = {
            "models": models,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/png;base64,"
                                + base64.b64encode(image).decode("ascii"),
                            },
                        },
                    ],
                }
            ],
        }
        if schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "observation", "strict": True, "schema": schema},
            }
            payload["provider"] = {"require_parameters": True}
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        if len(serialized) >= REQUEST_LIMIT:
            raise AcademicError("Screenshot is too large for the app's 20 MB request budget.")
        try:
            body = self.transport.post(self.config.key, serialized)
            return complete_text(body)
        except ApiError as failure:
            message = str(failure).replace(self.config.key, "[redacted]")
            raise ApiError(message, failure.status) from None
