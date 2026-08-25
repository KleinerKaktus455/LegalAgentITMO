from __future__ import annotations

import re
from typing import Any

from legal_multiagent.agents.common import planned, skip, store
from legal_multiagent.models import GuardReport
from legal_multiagent.state import AgentState


_CASE_ID_RE = re.compile(r"\b(\d{8,12})\b")
_CASE_NUM_RE = re.compile(r"\b\d{1,2}-\d+/\d{4}\b")


def guard_node(state: AgentState) -> dict[str, Any]:
    if not planned(state, "guard"):
        return skip("guard")

    db = store()
    draft = state.get("draft") or {}
    body = draft.get("body") or ""
    cited_ids = list(draft.get("cited_case_ids") or [])
    quotes = list(draft.get("cited_quotes") or [])
    issues: list[str] = []
    verified: list[str] = []
    dropped: list[str] = []

    for case_id in cited_ids + _CASE_ID_RE.findall(body):
        if db.exists(case_id):
            if case_id not in verified:
                verified.append(case_id)
        elif case_id in cited_ids:
            issues.append(f"ссылка на неизвестное дело {case_id}")

    for number in _CASE_NUM_RE.findall(body):
        if not db.find_by_number(number):
            issues.append(f"номер дела {number} не найден в индексе")

    for quote in quotes:
        fragment = (quote or "").strip()
        if len(fragment) < 40:
            continue
        found = False
        for case_id in verified or cited_ids:
            text = db.get_text(case_id)
            if fragment[:80] in text:
                found = True
                break
        brief = state.get("act_brief") or {}
        if not found and brief.get("fabula") and fragment[:80] in (brief.get("fabula") or ""):
            found = True
        if not found:
            dropped.append(fragment[:120])
            issues.append("цитата не подтверждена текстом акта из индекса")

    if state.get("risk") and not state.get("analogs"):
        issues.append("оценка риска без аналогов")

    report = GuardReport(
        ok=not issues,
        issues=issues,
        verified_case_ids=verified,
        dropped_quotes=dropped,
    )
    return {"guard": report.model_dump(), "steps_done": ["guard"]}
