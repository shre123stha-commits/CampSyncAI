"""Contract tests for the LLM retry loop, using a stubbed model."""

import pytest

from utils.llm_json import LLMOutputError, invoke_json


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    """Returns each queued response in turn and records the prompts it saw."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("FakeLLM called more times than expected")
        return FakeResponse(self.responses.pop(0))


def as_is(data):
    return data


def test_first_attempt_succeeds():
    llm = FakeLLM(['{"a": 1}'])
    assert invoke_json(llm, "p", as_is) == {"a": 1}
    assert len(llm.prompts) == 1


def test_markdown_fence_still_succeeds_first_time():
    llm = FakeLLM(['```json\n{"a": 1}\n```'])
    assert invoke_json(llm, "p", as_is) == {"a": 1}
    assert len(llm.prompts) == 1


def test_retry_after_unparseable_output():
    llm = FakeLLM(["not json at all", '{"a": 1}'])
    assert invoke_json(llm, "p", as_is) == {"a": 1}
    assert len(llm.prompts) == 2


def test_retry_prompt_includes_the_error():
    llm = FakeLLM(["garbage", '{"a": 1}'])
    invoke_json(llm, "original prompt", as_is)

    retry_prompt = llm.prompts[1]
    assert "original prompt" in retry_prompt
    assert "your previous response was rejected" in retry_prompt


def test_validation_failure_triggers_retry():
    calls = []

    def validator(data):
        calls.append(data)
        if data.get("ok") is not True:
            raise ValueError("field 'ok' must be true")
        return data

    llm = FakeLLM(['{"ok": false}', '{"ok": true}'])

    assert invoke_json(llm, "p", validator) == {"ok": True}
    assert len(calls) == 2
    assert "field 'ok' must be true" in llm.prompts[1]


def test_gives_up_after_budget_and_raises():
    llm = FakeLLM(["bad", "bad", "bad"])

    with pytest.raises(LLMOutputError):
        invoke_json(llm, "p", as_is, max_retries=2)

    assert len(llm.prompts) == 3


def test_zero_retries_means_one_attempt():
    llm = FakeLLM(["bad"])

    with pytest.raises(LLMOutputError):
        invoke_json(llm, "p", as_is, max_retries=0)

    assert len(llm.prompts) == 1


def test_transport_error_is_wrapped():
    class BrokenLLM:
        def invoke(self, prompt):
            raise ConnectionError("connection refused")

    with pytest.raises(LLMOutputError, match="LLM service error"):
        invoke_json(BrokenLLM(), "p", as_is)
