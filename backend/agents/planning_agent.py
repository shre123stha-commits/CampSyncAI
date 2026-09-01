"""Generates the study plan, then verifies it deterministically.

Flow:

    build prompt -> LLM -> tolerant parse -> schema validation
                        -> semantic validation -> retry with the error

Anything Python can compute (days remaining, priority band, whether a session
fits in a real free slot) is recomputed or checked here rather than trusted to
the model.
"""

from __future__ import annotations

from datetime import datetime

from config import LLM_MAX_RETRIES, get_logger, llm
from models.enums import PlanMode
from models.study_plan import PlannedItem, StudyPlanResponse
from prompts.planning_prompt import PLANNING_PROMPT
from scheduler.plan_validator import expected_priority, validate_plan
from scheduler.study_slots import extract_study_slots
from utils.llm_json import LLMOutputError, invoke_json
from utils.mode_prompt import get_mode_instruction
from utils.prompt_formatter import format_slots, format_tasks, format_timetable

logger = get_logger(__name__)


def _coerce_items(data) -> list[PlannedItem]:
    """Validate the raw parsed JSON into PlannedItem objects."""
    if isinstance(data, list):
        raw_items = data
    elif isinstance(data, dict):
        raw_items = data.get("plan")
        if raw_items is None:
            for key in ("tasks", "schedule", "items"):
                if isinstance(data.get(key), list):
                    raw_items = data[key]
                    break
        if raw_items is None:
            raise ValueError("Response is missing the 'plan' array.")
    else:
        raise ValueError("Response must be a JSON object with a 'plan' array.")

    if not isinstance(raw_items, list):
        raise ValueError("'plan' must be an array.")

    return [PlannedItem(**item) for item in raw_items if isinstance(item, dict)]


def _reconcile(items: list[PlannedItem], tasks) -> list[PlannedItem]:
    """Overwrite model-supplied values with Python-computed truth.

    Matching is done on (subject, work) with a fallback to subject alone,
    since the model sometimes lightly rewords the work description.
    """
    by_pair = {(t.subject, t.work): t for t in tasks}
    by_subject = {t.subject: t for t in tasks}

    for item in items:
        source = by_pair.get((item.subject, item.work)) or by_subject.get(
            item.subject
        )

        if source is not None:
            item.days_remaining = source.days_remaining
            item.deadline = source.deadline
            if not item.task_type:
                item.task_type = source.task_type

        # Priority is a pure function of days_remaining.
        item.priority = expected_priority(item.days_remaining)

    return items


def planning_agent(state):
    mode = PlanMode(state["mode"])

    logger.info("Planning agent: mode=%s", mode.value)

    tasks = list(state.get("assignments", [])) + list(
        state.get("classroom_tasks", [])
    )

    slots = extract_study_slots(state.get("timetable", []))

    today = datetime.today()

    # No work to schedule - return an empty plan rather than inventing one.
    if not tasks:
        logger.info("Planning agent: no tasks, returning empty plan.")
        state["study_plan"] = StudyPlanResponse(
            mode=mode,
            registration_no=state.get("registration_no", ""),
            generated_on=today.strftime("%d %B %Y"),
            plan=[],
        )
        return state

    base_prompt = PLANNING_PROMPT.format(
        today=today.strftime("%d %B %Y"),
        mode_instruction=get_mode_instruction(mode.value),
        timetable=format_timetable(state.get("timetable", [])),
        slots=format_slots(slots),
        tasks=format_tasks(tasks),
    )

    def validator(data) -> list[PlannedItem]:
        items = _reconcile(_coerce_items(data), tasks)

        problems = validate_plan(items, mode, slots)

        if problems:
            raise ValueError(
                "The plan breaks these rules:\n- " + "\n- ".join(problems[:5])
            )

        return items

    try:
        items = invoke_json(
            llm,
            base_prompt,
            validator,
            max_retries=LLM_MAX_RETRIES,
            label="planning",
        )

    except LLMOutputError as exc:
        # Best-effort fallback: accept a schema-valid plan even if it still
        # breaks a soft rule, rather than failing the request outright.
        logger.warning("Planning validation exhausted (%s); retrying loosely", exc)

        items = invoke_json(
            llm,
            base_prompt,
            lambda data: _reconcile(_coerce_items(data), tasks),
            max_retries=0,
            label="planning[relaxed]",
        )

    # Untimed modes must never carry timings.
    if not mode.includes_timings:
        for item in items:
            item.start_time = ""
            item.end_time = ""

    state["study_plan"] = StudyPlanResponse(
        mode=mode,
        registration_no=state.get("registration_no", ""),
        generated_on=today.strftime("%d %B %Y"),
        plan=items,
    )

    logger.info("Planning agent: generated %d item(s)", len(items))

    return state
