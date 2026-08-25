from __future__ import annotations

from typing import Any

from legal_multiagent.agents.common import planned, skip, store
from legal_multiagent.state import AgentState


def parser_node(state: AgentState) -> dict[str, Any]:
    if not planned(state, "parser"):
        return skip("parser")

    db = store()
    case = None
    case_id = state.get("case_id")
    number = state.get("case_number")

    if case_id:
        case = db.get(case_id)
    if case is None and number:
        found = db.find_by_number(number)
        case = found[0] if found else None
    if case is None and state.get("case"):
        return {"steps_done": ["parser:reuse"]}

    if case is None:
        if case_id or number:
            return skip(
                "parser",
                "карточка не найдена в индексе: проверьте --case-id / --case-number",
            )
        return skip("parser")

    return {
        "case": case.model_dump(),
        "case_id": case.case_id,
        "case_number": case.case_number,
        "gaps": list(case.gaps),
        "steps_done": ["parser"],
    }
