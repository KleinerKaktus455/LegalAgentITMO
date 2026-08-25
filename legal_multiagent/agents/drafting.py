from __future__ import annotations

from typing import Any

from legal_multiagent.agents.common import case_from_state, planned, skip
from legal_multiagent.llm import invoke_text
from legal_multiagent.models import AnalogCase, DraftDocument
from legal_multiagent.state import AgentState


def _fallback_draft(state: AgentState) -> DraftDocument:
    case = case_from_state(state)
    analogs = [AnalogCase.model_validate(item) for item in (state.get("analogs") or [])[:5]]
    cited = [a.case_id for a in analogs]
    lines = [
        "ЧЕРНОВИК ПОЗИЦИИ (без LLM, по структуре корпуса)",
        "",
        f"Запрос: {state.get('query')}",
    ]
    if case:
        lines += [
            f"Дело: {case.case_number} ({case.case_id})",
            f"Суд / судья: {case.court} / {case.judge}",
            f"Статья: {case.primary_article()}",
            f"Исход карточки: {case.card_result}",
            f"Исход акта: {case.document_result}",
        ]
    brief = state.get("act_brief") or {}
    if brief.get("fabula"):
        lines += ["", "Фабула из акта:", brief["fabula"][:600]]
    if analogs:
        lines += ["", "Опора на аналоги:"]
        for analog in analogs:
            lines.append(
                f"- {analog.case_number} / {analog.case_id}: {analog.article}; "
                f"{analog.document_result or analog.card_result}; {', '.join(analog.reasons)}"
            )
    risk = state.get("risk") or {}
    if risk.get("summary"):
        lines += ["", "Оценка практики:", risk["summary"]]
    appeal = state.get("appeal") or {}
    if appeal.get("summary"):
        lines += ["", "Апелляция:", appeal["summary"]]
    lines += [
        "",
        "Это черновик для юриста, не процессуальный документ и не юридическая консультация.",
    ]
    return DraftDocument(
        title="Черновик позиции по практике СОЮ",
        body="\n".join(lines),
        cited_case_ids=cited,
        cited_quotes=[brief["fabula"][:300]] if brief.get("fabula") else [],
    )


def drafting_node(state: AgentState) -> dict[str, Any]:
    if not planned(state, "draft"):
        return skip("draft")

    fallback = _fallback_draft(state)
    llm_body = invoke_text(
        (
            "Ты помощник адвоката. Пиши черновик на русском. "
            "Ссылайся только на переданные номера дел. Не выдумывай нормы и факты."
        ),
        (
            f"Запрос: {state.get('query')}\n"
            f"Карточка: {state.get('case') and {k: state['case'].get(k) for k in ('case_number','court','judge','card_result','document_result')}}\n"
            f"Квалификация: {state.get('qualification')}\n"
            f"Аналоги: {state.get('analogs')[:6] if state.get('analogs') else []}\n"
            f"Риск: {state.get('risk')}\n"
            f"Апелляция: {state.get('appeal')}\n"
            f"Краткая выжимка акта: {state.get('act_brief')}\n"
            "Напиши ходатайство или позицию на 1-2 страницы."
        ),
    )
    draft = fallback
    if llm_body:
        draft = DraftDocument(
            title=fallback.title,
            body=llm_body.strip(),
            cited_case_ids=fallback.cited_case_ids,
            cited_quotes=fallback.cited_quotes,
        )
    return {"draft": draft.model_dump(), "steps_done": ["draft"], "llm_used": bool(llm_body)}
