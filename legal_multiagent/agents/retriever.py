from __future__ import annotations

from typing import Any

from legal_multiagent.agents.common import case_from_state, planned, skip, store
from legal_multiagent.etl.fields import parse_article
from legal_multiagent.state import AgentState


def retriever_node(state: AgentState) -> dict[str, Any]:
    if not planned(state, "retriever"):
        return skip("retriever")

    db = store()
    case = case_from_state(state)
    query_article = state.get("query_article") or ""
    article_num = ""
    instance = ""
    region = ""
    judge = ""
    query_text = state.get("query") or ""
    exclude_id = ""

    if case:
        if case.charges:
            article_num = case.charges[0].article
        instance = case.instance
        region = case.region
        judge = case.judge
        exclude_id = case.case_id
        brief = state.get("act_brief") or {}
        if case.split_fabula:
            query_text = f"{query_text} {case.split_fabula}"
        elif brief.get("fabula"):
            query_text = f"{query_text} {brief['fabula']}"
        else:
            query_text = f"{query_text} {case.fabula_hint()}"

    if query_article:
        parsed = parse_article(query_article if query_article.startswith("ст") else f"ст. {query_article}")
        if not parsed["article"]:
            parsed = parse_article(f"ст. {query_article}")
        article_num = parsed["article"] or article_num

    analogs = db.search_analogs(
        article_num=article_num,
        instance=instance,
        region=region,
        judge=judge,
        query_text=query_text,
        exclude_id=exclude_id,
        limit=20,
    )
    gaps = []
    if not analogs:
        gaps.append("аналоги не найдены: увеличьте индекс (`python -m legal_multiagent ingest`)")
    return {
        "analogs": [a.model_dump() for a in analogs],
        "gaps": gaps,
        "steps_done": ["retriever"],
    }
