"""Full planning-agent behaviour with a stubbed LLM (no Ollama required)."""

import json

import pytest

import agents.planning_agent as planning_module
from models.enums import Priority
from models.task import Task
from models.timetable import Lecture


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return FakeResponse(self.responses.pop(0))


@pytest.fixture
def base_state():
    return {
        "registration_no": "24BAI1127",
        "timetable": [
            Lecture(
                day="Monday",
                start_time="09:00",
                end_time="10:00",
                subject="Maths",
            )
        ],
        "assignments": [
            Task(
                subject="Maths",
                task_type="Assignment",
                platform="LMS",
                deadline="12 August 2026",
                work="Solve problem set 3",
                days_remaining=2,
            )
        ],
        "classroom_tasks": [],
    }


def plan_json(**overrides):
    item = {
        "day": "Monday",
        "start_time": "",
        "end_time": "",
        "subject": "Maths",
        "task_type": "Assignment",
        "work": "Solve problem set 3",
        "deadline": "12 August 2026",
        "priority": "High",
        "days_remaining": 2,
        "reason": "Deadline is close.",
    }
    item.update(overrides)
    return json.dumps({"mode": "day_without_timings", "plan": [item]})


def test_happy_path(base_state, monkeypatch):
    monkeypatch.setattr(planning_module, "llm", FakeLLM([plan_json()]))

    state = {**base_state, "mode": "day_without_timings"}
    result = planning_module.planning_agent(state)

    plan = result["study_plan"]
    assert plan.mode.value == "day_without_timings"
    assert len(plan.plan) == 1
    assert plan.plan[0].subject == "Maths"
    assert plan.registration_no == "24BAI1127"


def test_no_tasks_returns_empty_plan_without_calling_the_llm(base_state):
    state = {**base_state, "mode": "day_without_timings", "assignments": []}

    # No LLM patched: any call would raise AttributeError.
    result = planning_module.planning_agent(state)

    assert result["study_plan"].plan == []


def test_days_remaining_is_overwritten_by_python(base_state, monkeypatch):
    """The model's arithmetic is never trusted."""
    monkeypatch.setattr(
        planning_module, "llm", FakeLLM([plan_json(days_remaining=99)])
    )

    state = {**base_state, "mode": "day_without_timings"}
    result = planning_module.planning_agent(state)

    assert result["study_plan"].plan[0].days_remaining == 2


def test_priority_is_recomputed_from_days_remaining(base_state, monkeypatch):
    monkeypatch.setattr(
        planning_module, "llm", FakeLLM([plan_json(priority="Low")])
    )

    state = {**base_state, "mode": "day_without_timings"}
    result = planning_module.planning_agent(state)

    assert result["study_plan"].plan[0].priority is Priority.HIGH


def test_timings_stripped_in_untimed_mode(base_state, monkeypatch):
    """Even if the model keeps emitting timings, they never reach the client.

    The validator rejects them first (triggering retries); the final strip is
    the belt-and-braces guarantee.
    """
    timed = plan_json(start_time="16:00", end_time="17:00")

    # 1 initial + 2 retries all rejected, then the relaxed attempt.
    monkeypatch.setattr(planning_module, "llm", FakeLLM([timed] * 4))

    state = {**base_state, "mode": "day_without_timings"}
    result = planning_module.planning_agent(state)

    item = result["study_plan"].plan[0]
    assert item.start_time == ""
    assert item.end_time == ""


def test_untimed_violation_is_retried(base_state, monkeypatch):
    """A plan with timings in an untimed mode is sent back to the model."""
    fake = FakeLLM([plan_json(start_time="16:00", end_time="17:00"), plan_json()])
    monkeypatch.setattr(planning_module, "llm", fake)

    state = {**base_state, "mode": "day_without_timings"}
    planning_module.planning_agent(state)

    assert len(fake.prompts) == 2
    assert "must not include timings" in fake.prompts[1]


def test_malformed_json_then_recovery(base_state, monkeypatch):
    fake = FakeLLM(["I cannot do that", plan_json()])
    monkeypatch.setattr(planning_module, "llm", fake)

    state = {**base_state, "mode": "day_without_timings"}
    result = planning_module.planning_agent(state)

    assert len(result["study_plan"].plan) == 1
    assert len(fake.prompts) == 2


def test_fenced_json_is_accepted(base_state, monkeypatch):
    fenced = f"```json\n{plan_json()}\n```"
    monkeypatch.setattr(planning_module, "llm", FakeLLM([fenced]))

    state = {**base_state, "mode": "day_without_timings"}
    result = planning_module.planning_agent(state)

    assert len(result["study_plan"].plan) == 1


def test_missing_plan_key_triggers_retry(base_state, monkeypatch):
    fake = FakeLLM(['{"mode": "day_without_timings"}', plan_json()])
    monkeypatch.setattr(planning_module, "llm", fake)

    state = {**base_state, "mode": "day_without_timings"}
    result = planning_module.planning_agent(state)

    assert len(result["study_plan"].plan) == 1
    assert len(fake.prompts) == 2


def test_bad_plan_falls_back_rather_than_failing(base_state, monkeypatch):
    """After the retry budget, a schema-valid plan is accepted."""
    timed = plan_json(start_time="03:00", end_time="04:00")

    # 3 validation failures (1 + 2 retries), then the relaxed attempt.
    fake = FakeLLM([timed, timed, timed, timed])
    monkeypatch.setattr(planning_module, "llm", fake)

    state = {**base_state, "mode": "day_with_timings"}
    result = planning_module.planning_agent(state)

    assert len(result["study_plan"].plan) == 1
