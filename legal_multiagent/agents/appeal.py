from __future__ import annotations

from typing import Any

from legal_multiagent.agents.common import case_from_state, planned, skip
from legal_multiagent.llm import invoke_text
from legal_multiagent.models import AnalogCase, AppealMemo
from legal_multiagent.state import AgentState


def appeal_node(state: AgentState) -> dict[str, Any]:
    if not planned(state, "appeal"):
        return skip("appeal")

    case = case_from_state(state)
    analogs = [AnalogCase.model_validate(item) for item in state.get("analogs") or []]
    appeal_like = [
        a
        for a in analogs
        if "апелляц" in (a.instance + a.card_result).lower() or a.instance.lower().startswith("апел")
    ]
    pool = appeal_like or analogs
    fates: dict[str, int] = {}
    for item in pool:
        key = item.card_result or item.document_result or "не указан"
        fates[key] = fates.get(key, 0) + 1

    suggestions = [
        "сверить квалификацию карточки и акта — расхождение часто даёт повод для жалобы",
        "смотреть отложения и возврат прокурору в хронике: это процессуальные зацепки",
        "не обещать отмену: в срезе апелляции типично оставление акта без изменения",
    ]
    if case and case.transferred_from:
        suggestions.append(f"нижестоящий суд: {case.transferred_from}")

    summary = f"По {len(pool)} сопоставимым делам типичные исходы: {fates}."
    comment = invoke_text(
        "Ты адвокат. Комментируй только переданные факты, без новых дел и цифр.",
        (
            f"Запрос: {state.get('query')}\nДело: {case.case_number if case else 'нет карточки'}\n"
            f"Исход карточки: {case.card_result if case else '-'}\n"
            f"Судьбы аналогов (не менять): {fates}\n"
            "2 предложения: на что смотреть в жалобе."
        ),
    )
    if comment:
        summary = summary + "\n\nКомментарий модели (не источник цифр): " + comment.strip()

    memo = AppealMemo(
        analog_count=len(pool),
        typical_fates=fates,
        summary=summary,
        suggestions=suggestions,
    )
    return {"appeal": memo.model_dump(), "steps_done": ["appeal"], "llm_used": bool(comment)}
