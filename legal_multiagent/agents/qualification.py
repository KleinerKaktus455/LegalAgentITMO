from __future__ import annotations

from typing import Any

from legal_multiagent.agents.common import case_from_state, planned, skip
from legal_multiagent.etl.fields import (
    PROCESS_ARTICLES,
    PUNISHMENT_ARTICLES,
    extract_articles_from_text,
)
from legal_multiagent.models import QualificationReport
from legal_multiagent.state import AgentState


def qualification_node(state: AgentState) -> dict[str, Any]:
    if not planned(state, "qualification"):
        return skip("qualification")

    case = case_from_state(state)
    query_article = state.get("query_article") or ""
    card: list[str] = []
    act: list[str] = []
    if case:
        card = [c.canonical or c.raw for c in case.charges if c.source == "card"]
        act = [c.canonical or c.raw for c in case.charges if c.source != "card"]
        if not act and case.act and case.act.text:
            act = [p["canonical"] for p in extract_articles_from_text(case.act.text[:6000]) if p["canonical"]]

    query_charges = [query_article] if query_article else []
    skip_nums = PUNISHMENT_ARTICLES | PROCESS_ARTICLES
    punishment = []
    for item in card + act:
        num = item.split()[0] if item else ""
        if num in PUNISHMENT_ARTICLES or num in PROCESS_ARTICLES:
            punishment.append(item)

    mismatches: list[str] = []
    if card and act:
        card_nums = {c.split()[0] for c in card if c}
        act_nums = {c.split()[0] for c in act if c} - skip_nums
        extra = act_nums - card_nums
        missing = card_nums - act_nums
        if extra:
            mismatches.append("в акте есть статьи, которых нет на карточке: " + ", ".join(sorted(extra)))
        if missing:
            mismatches.append("на карточке есть статьи, не найденные в акте: " + ", ".join(sorted(missing)))

    notes = []
    if punishment:
        notes.append("служебные статьи (69–80, 25, 76 и т.п.) отделены от состава")
    if query_article and case and query_article.split()[0] not in {
        (c.article or "") for c in case.charges
    }:
        notes.append("статья из запроса не совпадает со статьёй карточки")

    report = QualificationReport(
        card_charges=card,
        act_charges=act,
        query_charges=query_charges,
        mismatches=mismatches,
        punishment_articles=punishment,
        notes=notes,
    )
    return {"qualification": report.model_dump(), "steps_done": ["qualification"]}
