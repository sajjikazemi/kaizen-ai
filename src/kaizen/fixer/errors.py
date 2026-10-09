"""Shared error types/helpers so a Fixer-session failure reaches the CLI as
a short, human-readable message instead of a raw library/provider traceback.
"""
from __future__ import annotations

import json
from typing import Any


class FixerSessionError(RuntimeError):
    """Raised when a Fixer backend session fails. `str(exc)` is already a
    short, human-readable summary - safe to print directly without a
    traceback."""


def summarize_exception(exc: Exception) -> str:
    """Best-effort short summary of an exception, including picking the
    `error.message` out of OpenAI/Azure-style HTTP error bodies when
    present, instead of their verbose default `str()`.
    """
    body: Any = getattr(exc, "body", None)
    if isinstance(body, dict):
        message = body.get("error", {}).get("message") if isinstance(body.get("error"), dict) else None
        if message:
            return f"{type(exc).__name__}: {message}"
    if isinstance(body, str):
        try:
            parsed = json.loads(body)
            message = parsed.get("error", {}).get("message")
            if message:
                return f"{type(exc).__name__}: {message}"
        except (ValueError, AttributeError):
            pass

    text = str(exc).strip()
    first_line = text.splitlines()[0] if text else type(exc).__name__
    return first_line[:500]
