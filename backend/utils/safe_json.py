"""Tolerant parsing of JSON emitted by an LLM.

Local models routinely decorate their output: markdown fences, a
``<think>...</think>`` preamble from reasoning-tuned checkpoints, or a
sentence of commentary before the payload. A bare ``json.loads`` therefore
fails often enough to break a live demo.

``safe_json_parse`` strips the common decorations and extracts the first
balanced JSON value it finds.
"""

from __future__ import annotations

import json
import re
from typing import Any

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


class JSONParseError(ValueError):
    """Raised when no valid JSON value can be recovered from the text."""


def _strip_decorations(text: str) -> str:
    text = _THINK_BLOCK.sub("", text)

    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1)

    return text.strip()


def _extract_balanced(text: str) -> str | None:
    """Return the first balanced ``{...}`` or ``[...]`` block in *text*.

    Brackets appearing inside string literals are ignored.
    """
    start = None
    opener = closer = ""

    for index, char in enumerate(text):
        if char in "{[":
            start = index
            opener = char
            closer = "}" if char == "{" else "]"
            break

    if start is None:
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None


def safe_json_parse(raw: str) -> Any:
    """Parse JSON from a possibly-decorated LLM response.

    Raises:
        JSONParseError: if nothing parseable can be recovered.
    """
    if raw is None:
        raise JSONParseError("LLM returned no content")

    if not isinstance(raw, str):
        raw = str(raw)

    cleaned = _strip_decorations(raw)

    if not cleaned:
        raise JSONParseError("LLM returned an empty response")

    # Fast path: the whole thing is already valid JSON.
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    candidate = _extract_balanced(cleaned)

    if candidate is None:
        raise JSONParseError(
            f"No JSON object or array found in response: {cleaned[:200]!r}"
        )

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        # Last resort: trailing commas are the most common malformation.
        repaired = re.sub(r",(\s*[}\]])", r"\1", candidate)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            raise JSONParseError(
                f"Malformed JSON in LLM response: {exc}"
            ) from exc
