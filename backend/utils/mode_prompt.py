def get_mode_instruction(mode: str):

    instructions = {

        "day_with_timings": """
Generate a study plan ONLY for today.

Include exact study timings.

Use available free periods first.

Then use after-college time if required.

Schedule tasks according to urgency and deadlines.
""",

        "day_without_timings": """
Generate a study plan ONLY for today.

Do NOT include timings.

Only list the order in which the student should complete the tasks.

Prioritize urgent work.
""",

        "week_with_timings": """
Generate a study plan for the entire week.

Include study timings.

Distribute the workload evenly.

Do not overload one day.

Use free periods and after-college time.
""",

        "week_without_timings": """
Generate a study plan for the entire week.

Do NOT include timings.

Mention which tasks should be completed on each day.

Balance the workload throughout the week.
"""
    }

    return instructions.get(
        mode,
        "Generate the best study plan."
    )