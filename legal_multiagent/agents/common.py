from __future__ import annotations

from typing import Any

from legal_multiagent.models import CaseGraph
from legal_multiagent.state import AgentState
from legal_multiagent.store.sqlite_store import CaseStore


def planned(state: AgentState, name: str) -> bool:
    plan = state.get("plan") or []
    return name in plan


def case_from_state(state: AgentState) -> CaseGraph | None:
    payload = state.get("case")
    if not payload:
        return None
    return CaseGraph.model_validate(payload)


def store() -> CaseStore:
    return CaseStore()


def skip(name: str, reason: str = "") -> dict[str, Any]:
    update: dict[str, Any] = {"steps_done": [f"{name}:skip"]}
    if reason:
        update["gaps"] = [reason]
    return update
