"""Closed public models and validation for the office lab."""

from __future__ import annotations

import platform
import re
from typing import Any


class LabError(Exception):
    """A safe public error code; submitted data never appears in the message."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


PHASES = ("calibration", "discovery", "confirmation")
ARMS = ("A", "B", "C")
TERMINAL = ("completed", "failed", "aborted", "blocked", "timed_out")
FINAL_LIMIT = 65_536
HOSTS = {
    "work": ("desktop_work", "gpt-6-luna max", "gpt-6-luna", "max"),
    "cowork": ("claude_cowork", "haiku-5.5-medium", "claude-haiku-5-5", "medium"),
    "antigravity": ("antigravity", "gemini-3.8-flash-mid", "gemini-3.8-flash-medium", "medium"),
}


def controller_environment() -> dict[str, str]:
    system = {"Darwin": "macos", "Windows": "windows"}.get(platform.system(), "unsupported")
    architecture = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "amd64": "x64"}.get(
        platform.machine().lower(), "unknown"
    )
    return {"os": system, "arch": architecture, "source": "local_platform"}


def cells() -> list[dict[str, Any]]:
    return [
        {
            "id": f"{system}-{name}",
            "os": system,
            "host": values[0],
            "requested_model": values[1],
            "expected_model": values[2],
            "expected_effort": values[3],
        }
        for system in ("macos", "windows")
        for name, values in HOSTS.items()
    ]


def fields(data: dict[str, Any], allowed: set[str], required: set[str]) -> None:
    if not isinstance(data, dict) or set(data) - allowed or required - set(data):
        raise LabError("invalid_fields")


def text(value: Any, maximum: int = FINAL_LIMIT, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not value and not empty):
        raise LabError("invalid_text")
    if (
        len(value.encode("utf-8")) > maximum
        or any(ord(character) < 32 and character not in "\n\r\t" for character in value)
        or "\x7f" in value
    ):
        raise LabError("invalid_text")
    return value


def enum(value: Any, options: tuple[str, ...]) -> str:
    if not isinstance(value, str) or value not in options:
        raise LabError("invalid_enum")
    return value


def integer(value: Any, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise LabError("invalid_integer")
    return int(value)


def boolean(value: Any) -> bool:
    if type(value) is not bool:
        raise LabError("invalid_boolean")
    return bool(value)


def identifier(value: Any) -> str:
    result = text(value, 100)
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}", result):
        raise LabError("invalid_id")
    return result
