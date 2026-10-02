from langgraph.graph import END, START, StateGraph

from forge_advisor.graph.state import AdvisorState
from forge_advisor.services.analyzer import analyze_task
from forge_advisor.services.policy import make_response


def analyze_node(state: AdvisorState) -> dict:
    return {"analysis": analyze_task(state["task"])}


def policy_node(state: AdvisorState) -> dict:
    return {"response": make_response(state["task"], state["analysis"])}


def build_graph():
    builder = StateGraph(AdvisorState)
    builder.add_node("analyze_task", analyze_node)
    builder.add_node("apply_policy", policy_node)

    builder.add_edge(START, "analyze_task")
    builder.add_edge("analyze_task", "apply_policy")
    builder.add_edge("apply_policy", END)

    return builder.compile()


# Compile once at import time; the graph is stateless in Phase 1.
graph = build_graph()
