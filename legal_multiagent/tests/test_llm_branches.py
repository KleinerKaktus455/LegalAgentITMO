from __future__ import annotations

from pathlib import Path

import pytest

from legal_multiagent import config
from legal_multiagent.agents.act_reader import act_reader_node
from legal_multiagent.agents.appeal import appeal_node
from legal_multiagent.agents.drafting import drafting_node
from legal_multiagent.agents.risk import risk_node
from legal_multiagent.models import AnalogCase, CaseGraph, Charge, Event, JudicialAct
from legal_multiagent.store.sqlite_store import CaseStore


def _case_with_act(
    case_id: str,
    article_num: str = "105",
    act_text: str = "",
) -> CaseGraph:
    return CaseGraph(
        case_id=case_id,
        case_number=f"{case_id}-num",
        article=article_num,
        region="Москва",
        instance="Первая инстанция",
        judge="Иванов",
        source="test",
        card_result="Вынесен ПРИГОВОР",
        document_result="осуждение",
        charges=[Charge(article=article_num, canonical=article_num, source="card")],
        events=[Event(name="Судебное заседание", result="Отложено", date="01.01.2024")],
        act=JudicialAct(has_text=bool(act_text), text=act_text) if act_text else None,
    )


@pytest.fixture
def store(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config, "store_path", lambda: tmp_path / "llm_branches.sqlite")
    return CaseStore()


@pytest.mark.slow
def test_act_reader_uses_llm_for_act_text(store):
    text = (
        "УСТАНОВИЛ: 1 января 2024 года подсудимый совершил хищение чужого имущества. "
        "ПРИГОВОРИЛ: признать виновным по статье 158 части 2 УК РФ."
    )
    case = _case_with_act("act1", article_num="158", act_text=text)
    state = {"plan": ["act_reader"], "case": case.model_dump()}
    result = act_reader_node(state)
    brief = result["act_brief"]
    assert brief["available"]
    assert "статье 158" in brief["qualification_text"] or "158" in brief["fabula"] or "статье" in brief["resolutive"]
    assert result.get("llm_used") is True


@pytest.mark.slow
def test_risk_adds_llm_commentary(store):
    analogs = [
        AnalogCase(case_id="x", case_number="n1", score=1.0, article="105", card_result="Вынесен ПРИГОВОР"),
        AnalogCase(case_id="y", case_number="n2", score=0.9, article="105", card_result="Вынесен ПРИГОВОР"),
        AnalogCase(case_id="z", case_number="n3", score=0.8, article="105", card_result="Вынесен ПРИГОВОР"),
    ]
    state = {
        "plan": ["risk"],
        "analogs": [a.model_dump() for a in analogs],
        "query": "оцени риск",
    }
    result = risk_node(state)
    risk = result["risk"]
    assert result.get("llm_used") is True
    assert "Комментарий модели" in risk["summary"]


@pytest.mark.slow
def test_drafting_uses_llm_when_available(store):
    case = _case_with_act("draft1", article_num="105", act_text="")
    analog = AnalogCase(
        case_id="a1",
        case_number="02-0002/2024",
        score=0.9,
        article="105",
        document_result="осуждение",
        reasons=["статья"],
    )
    state = {
        "plan": ["draft"],
        "case": case.model_dump(),
        "analogs": [analog.model_dump()],
        "risk": {"summary": "риск высокий"},
        "appeal": {"summary": "апелляция маловероятна"},
        "act_brief": {"fabula": "Фабула"},
        "query": "составь позицию",
    }
    result = drafting_node(state)
    draft = result["draft"]
    assert result.get("llm_used") is True
    assert draft["body"]
    assert len(draft["body"]) > 200


@pytest.mark.slow
def test_appeal_adds_llm_commentary(store):
    analogs = [
        AnalogCase(case_id="a1", case_number="n1", score=1.0, article="105", card_result="Оставлено без изменения", instance="Апелляция"),
        AnalogCase(case_id="a2", case_number="n2", score=0.9, article="105", card_result="Оставлено без изменения", instance="Апелляция"),
    ]
    state = {
        "plan": ["appeal"],
        "analogs": [a.model_dump() for a in analogs],
        "query": "апелляция",
    }
    result = appeal_node(state)
    appeal = result["appeal"]
    assert result.get("llm_used") is True
    assert "Комментарий модели" in appeal["summary"]
