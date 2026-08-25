from __future__ import annotations

from typing import Any

from legal_multiagent.agents.common import case_from_state, planned, skip
from legal_multiagent.state import AgentState


def timeline_node(state: AgentState) -> dict[str, Any]:
    if not planned(state, "timeline"):
        return skip("timeline")

    case = case_from_state(state)
    if case is None:
        return skip("timeline", "нет нормализованной карточки для хроники")

    events = case.events
    postponements = sum(1 for e in events if "отложен" in (e.result + e.name).lower())
    hearings = sum(1 for e in events if "судебное заседание" in (e.name + e.result).lower())
    prelim = any("предварительн" in e.name.lower() for e in events)
    returned = any("прокурор" in (e.result + e.name).lower() for e in events)
    suspended = any("приостанов" in (e.result + e.name).lower() for e in events)

    summary = (
        f"{len(events)} событий; заседаний: {hearings}; отложений: {postponements}; "
        f"предварительное слушание: {'да' if prelim else 'нет'}."
    )
    if not events:
        summary = "Движение дела в карточке отсутствует (часто так в апелляции)."

    return {
        "timeline": {
            "events": [e.model_dump() for e in events],
            "n_events": len(events),
            "hearings": hearings,
            "postponements": postponements,
            "preliminary_hearing": prelim,
            "returned_to_prosecutor": returned,
            "suspended": suspended,
            "entry_date": case.entry_date,
            "result_date": case.result_date,
            "summary": summary,
        },
        "steps_done": ["timeline"],
    }
