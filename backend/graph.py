"""LangGraph pipeline.

    START -> academic_agent -> classroom_agent -> planning_agent -> END

The self-correcting retry loop lives inside `planning_agent` (see
`utils.llm_json.invoke_json`), where it can feed the specific validation
error back into the prompt.
"""

from langgraph.graph import END, START, StateGraph

from agents.academic_agent import academic_agent
from agents.classroom_agent import classroom_agent
from agents.planning_agent import planning_agent
from state import PlannerState

builder = StateGraph(PlannerState)

builder.add_node("academic_agent", academic_agent)
builder.add_node("classroom_agent", classroom_agent)
builder.add_node("planning_agent", planning_agent)

builder.add_edge(START, "academic_agent")
builder.add_edge("academic_agent", "classroom_agent")
builder.add_edge("classroom_agent", "planning_agent")
builder.add_edge("planning_agent", END)

graph = builder.compile()
