from __future__ import annotations

from typing import Any

from legal_multiagent.agents.common import case_from_state, planned, skip, store
from legal_multiagent.llm import invoke_text
from legal_multiagent.models import AnalogCase, RiskReport
from legal_multiagent.state import AgentState


def _fmt_dist(dist: dict[str, int]) -> str:
    if not dist:
        return "нет данных"
    total = sum(dist.values()) or 1
    parts = [f"{k}: {v} ({100 * v / total:.0f}%)" for k, v in sorted(dist.items(), key=lambda x: -x[1])]
    return "; ".join(parts)


def risk_node(state: AgentState) -> dict[str, Any]:
    if not planned(state, "risk"):
        return skip("risk")

    db = store()
    case = case_from_state(state)
    analogs = [AnalogCase.model_validate(item) for item in state.get("analogs") or []]
    article_num = ""
    if case and case.charges:
        article_num = case.charges[0].article
    elif state.get("query_article"):
        article_num = state["query_article"].split()[0]

    card_dist = db.result_distribution(analogs, "card_result")
    doc_dist = db.result_distribution(analogs, "document_result")
    judge_profile = db.judge_profile(case.judge) if case else {}
    region_profile = db.region_profile(case.region, article_num) if case else {}

    caveats = [
        "это распределение по загруженному срезу корпуса, не прогноз суда",
        "оправдательных в базе почти нет — не обещать оправдание",
        "карточка «Вынесен ПРИГОВОР» не равна обвинительному приговору",
    ]
    if case and case.act and not case.act.has_text:
        caveats.append("у текущего дела нет текста акта — вилка наказания ненадёжна")
    if len(analogs) < 8:
        caveats.append("мало аналогов, оценка грубая")

    summary = (
        f"По {len(analogs)} аналогам исход карточки: {_fmt_dist(card_dist)}. "
        f"Исход акта: {_fmt_dist(doc_dist)}."
    )
    if case and case.card_result:
        summary += f" У самого дела в карточке уже стоит: {case.card_result}."

    comment = invoke_text(
        "Ты помощник адвоката. Прокомментируй статистику, не меняя и не добавляя цифры.",
        (
            f"Запрос: {state.get('query')}\nГотовая статистика (не менять):\n{summary}\n"
            "2 предложения: что это значит для защиты. Без новых чисел и дел."
        ),
    )
    if comment:
        summary = summary + "\n\nКомментарий модели (не источник цифр): " + comment.strip()

    report = RiskReport(
        analog_count=len(analogs),
        card_result_dist=card_dist,
        document_result_dist=doc_dist,
        judge_profile=judge_profile,
        region_profile=region_profile,
        summary=summary,
        caveats=caveats,
    )
    return {"risk": report.model_dump(), "steps_done": ["risk"], "llm_used": bool(comment)}
