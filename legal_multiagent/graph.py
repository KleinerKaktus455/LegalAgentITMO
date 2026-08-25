from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from legal_multiagent.agents.act_reader import act_reader_node
from legal_multiagent.agents.appeal import appeal_node
from legal_multiagent.agents.drafting import drafting_node
from legal_multiagent.agents.guard import guard_node
from legal_multiagent.agents.orchestrator import orchestrator_node
from legal_multiagent.agents.parser import parser_node
from legal_multiagent.agents.qualification import qualification_node
from legal_multiagent.agents.respond import respond_node
from legal_multiagent.agents.retriever import retriever_node
from legal_multiagent.agents.risk import risk_node
from legal_multiagent.agents.timeline import timeline_node
from legal_multiagent.state import AgentState


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("parser", parser_node)
    graph.add_node("timeline", timeline_node)
    graph.add_node("act_reader", act_reader_node)
    graph.add_node("qualification", qualification_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("risk", risk_node)
    graph.add_node("appeal", appeal_node)
    graph.add_node("draft", drafting_node)
    graph.add_node("guard", guard_node)
    graph.add_node("respond", respond_node)

    graph.add_edge(START, "orchestrator")
    graph.add_edge("orchestrator", "parser")
    graph.add_edge("parser", "timeline")
    graph.add_edge("timeline", "act_reader")
    graph.add_edge("act_reader", "qualification")
    graph.add_edge("qualification", "retriever")
    graph.add_edge("retriever", "risk")
    graph.add_edge("risk", "appeal")
    graph.add_edge("appeal", "draft")
    graph.add_edge("draft", "guard")
    graph.add_edge("guard", "respond")
    graph.add_edge("respond", END)
    return graph.compile()


_APP = None


def get_app():
    global _APP
    if _APP is None:
        _APP = build_graph()
    return _APP


def run_agent(
    query: str,
    case_id: str | None = None,
    case_number: str | None = None,
    playbook: str | None = None,
) -> dict:
    app = get_app()
    state: dict = {
        "query": query,
        "case_id": case_id,
        "case_number": case_number,
        "steps_done": [],
        "gaps": [],
        "errors": [],
        "analogs": [],
    }
    if playbook:
        state["playbook"] = playbook
    return app.invoke(state)
