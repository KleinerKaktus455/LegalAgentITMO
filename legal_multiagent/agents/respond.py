from __future__ import annotations

from typing import Any

from legal_multiagent.agents.common import case_from_state, planned, skip
from legal_multiagent.state import AgentState


def _render(state: AgentState) -> str:
    lines: list[str] = []
    playbook = state.get("playbook") or ""
    lines.append(f"Плейбук: {playbook}")
    lines.append("")

    case = case_from_state(state)
    if case:
        lines += [
            "## Досье",
            f"- Номер: {case.case_number}  |  id: {case.case_id}",
            f"- Источник: {case.source or '—'}  |  вид: {case.kind or case.case_type or '—'}",
            f"- Инстанция: {case.instance}  |  {case.court}  |  судья {case.judge}",
            f"- Регион: {case.region}",
            f"- Статья: {case.primary_article() or '—'}",
            f"- Исход карточки: {case.card_result or '—'}",
            f"- Исход акта: {case.document_result or '—'}",
        ]
        if case.gaps:
            lines.append("- Пробелы карточки: " + "; ".join(case.gaps))
        lines.append("")

    timeline = state.get("timeline")
    if timeline:
        lines += ["## Хроника", timeline.get("summary", ""), ""]
        for event in (timeline.get("events") or [])[:12]:
            lines.append(
                f"- {event.get('date', '')} {event.get('name', '')} → {event.get('result', '')}".strip()
            )
        lines.append("")

    brief = state.get("act_brief")
    if brief:
        lines.append("## Судебный акт")
        if not brief.get("available"):
            lines.append("Текста акта нет — опираемся только на карточку.")
        else:
            if brief.get("fabula"):
                lines.append("Фабула: " + brief["fabula"][:500])
            if brief.get("resolutive"):
                lines.append("Резолютивка: " + brief["resolutive"][:400])
            if brief.get("special_procedure"):
                lines.append("Признак особого порядка: да")
        lines.append("")

    qual = state.get("qualification")
    if qual:
        lines += [
            "## Квалификация",
            "Карточка: " + (", ".join(qual.get("card_charges") or []) or "—"),
            "Акт: " + (", ".join(qual.get("act_charges") or []) or "—"),
        ]
        for item in qual.get("mismatches") or []:
            lines.append("- " + item)
        lines.append("")

    analogs = state.get("analogs") or []
    if analogs:
        lines.append(f"## Аналоги ({len(analogs)})")
        for analog in analogs[:10]:
            lines.append(
                f"- {analog.get('case_number')} / {analog.get('case_id')}: "
                f"{analog.get('kind') or analog.get('article') or '—'}; "
                f"{analog.get('document_result') or analog.get('card_result') or '—'}; "
                f"score={analog.get('score')} ({', '.join(analog.get('reasons') or [])})"
            )
            if analog.get("fabula"):
                lines.append("  " + analog["fabula"][:220])
        lines.append("")

    risk = state.get("risk")
    if risk:
        lines += ["## Оценка практики", risk.get("summary", "")]
        for caveat in risk.get("caveats") or []:
            lines.append("- ограничение: " + caveat)
        lines.append("")

    appeal = state.get("appeal")
    if appeal:
        lines += ["## Апелляция", appeal.get("summary", "")]
        for item in appeal.get("suggestions") or []:
            lines.append("- " + item)
        lines.append("")

    draft = state.get("draft")
    if draft:
        lines += ["## Черновик", draft.get("body", ""), ""]

    guard = state.get("guard")
    if guard:
        status = "ок" if guard.get("ok") else "есть замечания"
        lines += ["## Проверка ссылок: " + status]
        for issue in guard.get("issues") or []:
            lines.append("- " + issue)
        lines.append("")

    extra_gaps = [g for g in (state.get("gaps") or []) if g]
    if extra_gaps:
        lines += ["## Чего в данных нет", *[f"- {g}" for g in extra_gaps]]

    lines += [
        "",
        "Ответ основан на индексе карточек СОЮ. Это не юридическая консультация и не предсказание конкретного суда.",
    ]
    return "\n".join(lines).strip()


def respond_node(state: AgentState) -> dict[str, Any]:
    if not planned(state, "respond"):
        return skip("respond")

    # Финальный текст собирается только из Case Graph и индекса.
    # LLM сюда не пускаем: иначе появляются выдуманные номера дел.
    rendered = _render(state)
    return {"final_answer": rendered, "steps_done": ["respond"]}
