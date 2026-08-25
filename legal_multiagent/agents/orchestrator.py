from __future__ import annotations

import re
from typing import Any

from legal_multiagent.etl.fields import extract_articles_from_text
from legal_multiagent.llm import invoke_json
from legal_multiagent.state import AgentState

PLAYBOOKS: dict[str, list[str]] = {
    "dossier": ["parser", "timeline", "act_reader", "qualification", "respond"],
    "analogs": ["parser", "qualification", "retriever", "respond"],
    "risk": ["parser", "timeline", "act_reader", "qualification", "retriever", "risk", "guard", "respond"],
    "appeal": [
        "parser",
        "timeline",
        "act_reader",
        "qualification",
        "retriever",
        "appeal",
        "draft",
        "guard",
        "respond",
    ],
    "draft": [
        "parser",
        "act_reader",
        "qualification",
        "retriever",
        "draft",
        "guard",
        "respond",
    ],
    "full": [
        "parser",
        "timeline",
        "act_reader",
        "qualification",
        "retriever",
        "risk",
        "appeal",
        "draft",
        "guard",
        "respond",
    ],
}


def _rule_playbook(query: str, has_case: bool) -> str:
    text = (query or "").lower()
    if re.search(r"апелляц|жалоб", text):
        return "appeal"
    if re.search(r"напиши|черновик|ходатайств|позици", text):
        return "draft"
    if re.search(r"шанс|риск|исход|прекращ|срок|вероят", text):
        return "risk"
    if re.search(r"похож|аналог|практик|прецедент", text):
        return "analogs"
    if re.search(r"разбер|досье|хроник|что произошло|лент", text):
        return "dossier"
    if has_case:
        return "full"
    return "risk"


def orchestrator_node(state: AgentState) -> dict[str, Any]:
    query = state.get("query") or ""
    has_case = bool(state.get("case_id") or state.get("case_number") or state.get("case"))
    playbook = state.get("playbook") or _rule_playbook(query, has_case)

    llm_choice = invoke_json(
        "Ты маршрутизатор юридического ассистента. Выбери playbook.",
        (
            "Допустимые playbook: dossier, analogs, risk, appeal, draft, full.\n"
            f"Запрос: {query}\nЕсть карточка дела: {has_case}\n"
            'Верни JSON {"playbook": "..."}'
        ),
    )
    if llm_choice and llm_choice.get("playbook") in PLAYBOOKS:
        playbook = str(llm_choice["playbook"])

    if playbook not in PLAYBOOKS:
        playbook = "full" if has_case else "risk"

    articles = extract_articles_from_text(query)
    query_article = articles[0]["canonical"] if articles else state.get("query_article") or ""

    return {
        "playbook": playbook,
        "plan": PLAYBOOKS[playbook],
        "query_article": query_article,
        "llm_used": llm_choice is not None,
        "steps_done": [f"orchestrator:{playbook}"],
    }
