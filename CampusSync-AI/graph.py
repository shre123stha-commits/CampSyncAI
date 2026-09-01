from langgraph.graph import StateGraph, START, END

from state import PlannerState
from agents.planning_agent import planning_agent

from agents.academic_agent import academic_agent
from agents.classroom_agent import classroom_agent
from agents.scheduling_agent import scheduling_agent
from agents.formatter_agent import formatter_agent


builder = StateGraph(PlannerState)

builder.add_node("academic_agent", academic_agent)
builder.add_node("classroom_agent", classroom_agent)
builder.add_node("planning_agent", planning_agent)
#builder.add_node("formatter_agent", formatter_agent)


builder.add_edge(START, "academic_agent")
builder.add_edge("academic_agent", "classroom_agent")
builder.add_edge("classroom_agent", "planning_agent")
builder.add_edge("planning_agent", END)
#builder.add_edge("formatter_agent", END)


graph = builder.compile()