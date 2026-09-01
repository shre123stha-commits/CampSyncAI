"""Invoke an LLM and get back validated, structured data.

Wraps every LLM boundary in the same contract:

    prompt -> invoke -> tolerant parse -> validate -> retry on failure

The retry feeds the specific error back to the model, which is far more
effective than simply asking again.
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from config import LLM_MAX_RETRIES, get_logger
from utils.safe_json import JSONParseError, safe_json_parse

logger = get_logger(__name__)

T = TypeVar("T")


class LLMOutputError(RuntimeError):
    """The model could not produce valid output within the retry budget."""


_RETRY_SUFFIX = """

==================================================

IMPORTANT — your previous response was rejected.

Error:
{error}

Return ONLY valid JSON matching the schema exactly.
Do not include markdown fences, explanations, or any text outside the JSON.
"""


def invoke_json(
    llm,
    prompt: str,
    validator: Callable[[Any], T],
    *,
    max_retries: int = LLM_MAX_RETRIES,
    label: str = "llm",
) -> T:
    """Call *llm* with *prompt* until *validator* accepts the parsed output.

    Args:
        llm: A LangChain chat model.
        prompt: The fully formatted prompt.
        validator: Receives the parsed JSON and returns the validated object.
            Should raise on invalid input.
        max_retries: Additional attempts after the first.
        label: Used in log messages.

    Returns:
        Whatever *validator* returns.

    Raises:
        LLMOutputError: if every attempt fails.
    """
    last_error: Exception | None = None
    current_prompt = prompt

    for attempt in range(max_retries + 1):
        try:
            response = llm.invoke(current_prompt)
        except Exception as exc:  # noqa: BLE001 - surfaced as LLMOutputError
            logger.error("%s: LLM call failed: %s", label, exc)
            raise LLMOutputError(f"LLM service error: {exc}") from exc

        content = getattr(response, "content", response)

        try:
            parsed = safe_json_parse(content)
            return validator(parsed)

        except (JSONParseError, ValueError, TypeError, KeyError) as exc:
            last_error = exc
            logger.warning(
                "%s: attempt %d/%d rejected: %s",
                label,
                attempt + 1,
                max_retries + 1,
                exc,
            )

            if attempt < max_retries:
                current_prompt = prompt + _RETRY_SUFFIX.format(error=exc)

    raise LLMOutputError(
        f"{label}: no valid output after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )
