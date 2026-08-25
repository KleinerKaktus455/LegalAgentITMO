from __future__ import annotations

import re
from typing import Any

from legal_multiagent.agents.common import case_from_state, planned, skip
from legal_multiagent.llm import invoke_json
from legal_multiagent.models import ActBrief
from legal_multiagent.state import AgentState


def _slice_after(text: str, marker: str, limit: int = 1800) -> str:
    match = re.search(marker, text, re.IGNORECASE)
    if not match:
        return ""
    return text[match.end() : match.end() + limit].strip()


def _heuristic_brief(text: str) -> ActBrief:
    fabula = _slice_after(text, r"УСТАНОВИЛ[:\s]", 2000)
    resolutive = _slice_after(text, r"(ПРИГОВОРИЛ|ПОСТАНОВИЛ)[:\s]", 1200)
    mitigating = ""
    aggravating = ""
    mit = re.search(r"смягчающ\w+\s+обстоятельств\w*[:\s]+(.{20,400})", text, re.IGNORECASE)
    agg = re.search(r"отягчающ\w+\s+обстоятельств\w*[:\s]+(.{20,400})", text, re.IGNORECASE)
    if mit:
        mitigating = mit.group(1).strip()
    if agg:
        aggravating = agg.group(1).strip()
    special = bool(re.search(r"особом порядке|особого производства|гл\.?\s*40", text, re.IGNORECASE))
    quotes = []
    if fabula:
        quotes.append({"kind": "fabula", "text": fabula[:400]})
    if resolutive:
        quotes.append({"kind": "resolutive", "text": resolutive[:400]})
    return ActBrief(
        available=True,
        header=text[:400],
        fabula=fabula,
        qualification_text=_slice_after(text, r"предусмотренн\w+", 400),
        mitigating=mitigating,
        aggravating=aggravating,
        special_procedure=special,
        resolutive=resolutive,
        quotes=quotes,
        notes=["разбор акта эвристикой"],
    )


def act_reader_node(state: AgentState) -> dict[str, Any]:
    if not planned(state, "act_reader"):
        return skip("act_reader")

    case = case_from_state(state)
    if case is None:
        return skip("act_reader", "нет карточки для чтения акта")
    if case.split_header or case.split_fabula or case.split_resolutive:
        brief = ActBrief(
            available=True,
            header=case.split_header,
            fabula=case.split_fabula,
            resolutive=case.split_resolutive,
            quotes=[
                {"kind": "fabula", "text": case.split_fabula[:400]},
                {"kind": "resolutive", "text": case.split_resolutive[:400]},
            ],
            notes=["текст взят из parquet-сплитов text_1 / text_2 / text_3"],
        )
        return {"act_brief": brief.model_dump(), "steps_done": ["act_reader:splits"]}
    if not case.act or not case.act.has_text:
        brief = ActBrief(available=False, notes=["текста судебного акта в карточке нет"])
        return {
            "act_brief": brief.model_dump(),
            "gaps": ["нет текста судебного акта"],
            "steps_done": ["act_reader:empty"],
        }

    brief = _heuristic_brief(case.act.text)
    llm_data = invoke_json(
        "Ты юрист-аналитик. Извлеки блоки из судебного акта. Не выдумывай факты.",
        (
            "Верни JSON со ключами header, fabula, qualification_text, mitigating, "
            "aggravating, special_procedure (bool), resolutive.\n\n"
            f"Текст акта:\n{case.act.text[:9000]}"
        ),
    )
    notes = list(brief.notes)
    if llm_data:
        brief = ActBrief(
            available=True,
            header=str(llm_data.get("header") or brief.header),
            fabula=str(llm_data.get("fabula") or brief.fabula),
            qualification_text=str(llm_data.get("qualification_text") or brief.qualification_text),
            mitigating=str(llm_data.get("mitigating") or brief.mitigating),
            aggravating=str(llm_data.get("aggravating") or brief.aggravating),
            special_procedure=bool(llm_data.get("special_procedure", brief.special_procedure)),
            resolutive=str(llm_data.get("resolutive") or brief.resolutive),
            quotes=brief.quotes,
            notes=["разбор акта уточнён LLM"],
        )
        notes = brief.notes
    brief.notes = notes
    return {"act_brief": brief.model_dump(), "steps_done": ["act_reader"], "llm_used": bool(llm_data)}
