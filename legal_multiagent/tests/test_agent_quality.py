from __future__ import annotations

from pathlib import Path

import pytest

from legal_multiagent.agents import act_reader, common, guard, parser, qualification, respond, retriever, risk, timeline
from legal_multiagent.agents.act_reader import act_reader_node
from legal_multiagent.agents.guard import guard_node
from legal_multiagent.agents.orchestrator import PLAYBOOKS, _rule_playbook, orchestrator_node
from legal_multiagent.agents.parser import parser_node
from legal_multiagent.agents.qualification import qualification_node
from legal_multiagent.agents.respond import respond_node
from legal_multiagent.agents.retriever import retriever_node
from legal_multiagent.agents.risk import risk_node
from legal_multiagent.agents.timeline import timeline_node
from legal_multiagent.models import (
    ActBrief,
    AnalogCase,
    CaseGraph,
    Charge,
    DraftDocument,
    Event,
    JudicialAct,
)
from legal_multiagent.store.sqlite_store import CaseStore


def _temp_store(tmp_path: Path) -> CaseStore:
    return CaseStore(path=tmp_path / "quality.sqlite")


def _case(
    case_id: str,
    article_num: str,
    region: str,
    instance: str,
    judge: str,
    fabula: str,
    card_result: str = "Вынесен ПРИГОВОР",
    document_result: str = "осуждение",
    events: list[Event] | None = None,
    act_text: str = "",
    split_header: str = "",
    split_fabula: str = "",
    split_resolutive: str = "",
    case_number: str = "",
) -> CaseGraph:
    return CaseGraph(
        case_id=case_id,
        case_number=case_number or f"{case_id}-num",
        article=article_num,
        region=region,
        instance=instance,
        judge=judge,
        source="test",
        split_header=split_header,
        split_fabula=split_fabula,
        split_resolutive=split_resolutive,
        card_result=card_result,
        document_result=document_result,
        charges=[Charge(article=article_num, canonical=article_num, source="card")],
        events=events or [],
        act=JudicialAct(has_text=bool(act_text), text=act_text) if act_text else None,
    )


@pytest.mark.parametrize(
    "query,expected",
    [
        ("найди похожие дела по статье 105", "analogs"),
        ("оцени риск исхода", "risk"),
        ("напиши апелляционную жалобу", "appeal"),
        ("разбери досье по делу", "dossier"),
        ("составь черновик позиции", "draft"),
    ],
)
def test_rule_playbook_routing(query: str, expected: str):
    assert _rule_playbook(query, has_case=False) == expected


def test_playbook_structure():
    for name, plan in PLAYBOOKS.items():
        assert plan[0] == "parser", f"{name} should start with parser"
        assert plan[-1] == "respond", f"{name} should end with respond"
    assert "retriever" in PLAYBOOKS["analogs"]
    assert "retriever" in PLAYBOOKS["risk"]
    assert "risk" in PLAYBOOKS["risk"]
    assert "appeal" in PLAYBOOKS["appeal"]
    assert "draft" in PLAYBOOKS["appeal"]
    assert "draft" in PLAYBOOKS["draft"]


def test_parser_node_finds_case(tmp_path: Path, monkeypatch):
    store = _temp_store(tmp_path)
    case = _case("c1", "105", "Москва", "Первая инстанция", "Иванов", "фабула")
    store.upsert(case)

    monkeypatch.setattr(parser, "store", lambda: store)
    state = {"plan": ["parser"], "case_id": "c1", "query": "разбери дело"}
    result = parser_node(state)
    assert result["steps_done"] == ["parser"]
    assert result["case_id"] == "c1"
    assert result["case_number"] == "c1-num"
    assert result["case"]["case_id"] == "c1"


def test_parser_node_missing_case(tmp_path: Path, monkeypatch):
    store = _temp_store(tmp_path)
    monkeypatch.setattr(parser, "store", lambda: store)
    state = {"plan": ["parser"], "case_id": "missing", "query": "разбери дело"}
    result = parser_node(state)
    assert result["steps_done"] == ["parser:skip"]
    assert "карточка не найдена" in result["gaps"][0]


def test_timeline_node_counts_events():
    events = [
        Event(name="Регистрация", result="", date="01.01.2023"),
        Event(name="Судебное заседание", result="Отложено", date="15.02.2023"),
        Event(name="Судебное заседание", result="", date="20.03.2023"),
    ]
    case = _case("c2", "105", "Москва", "Первая инстанция", "Иванов", "фабула", events=events)
    state = {"plan": ["timeline"], "case": case.model_dump()}
    result = timeline_node(state)
    timeline = result["timeline"]
    assert timeline["n_events"] == 3
    assert timeline["hearings"] == 2
    assert timeline["postponements"] == 1
    assert "заседаний: 2" in timeline["summary"]


def test_qualification_node_detects_mismatch():
    case = _case(
        "c3",
        "105",
        "Москва",
        "Первая инстанция",
        "Иванов",
        "фабула",
    )
    case.charges.append(Charge(article="322", canonical="322", source="act_text"))
    state = {"plan": ["qualification"], "case": case.model_dump(), "query_article": ""}
    result = qualification_node(state)
    qual = result["qualification"]
    assert any("в акте есть статьи" in m for m in qual["mismatches"])


def test_act_reader_extracts_from_splits():
    case = _case(
        "c4",
        "105",
        "Москва",
        "Первая инстанция",
        "Иванов",
        "",
        split_header="Шапка",
        split_fabula="Фабула дела",
        split_resolutive="Резолютивка",
    )
    state = {"plan": ["act_reader"], "case": case.model_dump()}
    result = act_reader_node(state)
    brief = result["act_brief"]
    assert brief["available"]
    assert brief["fabula"] == "Фабула дела"
    assert brief["resolutive"] == "Резолютивка"
    assert "act_reader:splits" in result["steps_done"]


def test_retriever_node_returns_relevant_analogs(tmp_path: Path, monkeypatch):
    store = _temp_store(tmp_path)
    target = _case(
        "target",
        "105",
        "Москва",
        "Первая инстанция",
        "Иванов",
        "убийство ревность нож",
    )
    store.upsert(target)

    analogs = [
        _case("a1", "105", "Москва", "Первая инстанция", "Иванов", "убийство ревность нож", document_result="осуждение"),
        _case("a2", "105", "Москва", "Первая инстанция", "Петров", "убийство ссора нож", document_result="осуждение"),
        _case("a3", "105", "СПб", "Первая инстанция", "Сидоров", "убийство дорога", document_result="осуждение"),
        _case("a4", "158", "Москва", "Первая инстанция", "Иванов", "кража кошелек", document_result="осуждение"),
    ]
    for a in analogs:
        store.upsert(a)

    monkeypatch.setattr(retriever, "store", lambda: store)
    state = {
        "plan": ["retriever"],
        "case": target.model_dump(),
        "query": "убийство ревность нож",
        "query_article": "105",
    }
    result = retriever_node(state)
    found = result["analogs"]
    assert len(found) > 0
    assert all(0 <= a["score"] <= 1 for a in found)
    assert found[0]["score"] == 1.0
    ids = [a["case_id"] for a in found]
    assert "target" not in ids
    top5 = ids[:5]
    article_hits = sum(1 for a in found[:5] if a["article"] == "105")
    region_hits = sum(1 for a in found[:5] if a["region"] == "Москва")
    # a4 (ст.158, Москва, Иванов) может обогнать a3 (ст.105, СПб) из-за веса судьи+региона
    assert article_hits >= 3, f"too few same-article analogs in top 5: {top5}"
    assert region_hits >= 3, f"too few same-region analogs in top 5: {top5}"


def test_respond_node_uses_only_state_facts():
    case = _case("r1", "105", "Москва", "Первая инстанция", "Иванов", "фабула", case_number="02-0001/2024")
    analog = AnalogCase(
        case_id="a1",
        case_number="02-0002/2024",
        score=0.85,
        reasons=["статья"],
        article="105",
        document_result="осуждение",
    )
    state = {
        "plan": ["respond"],
        "case": case.model_dump(),
        "timeline": {"summary": "3 события"},
        "analogs": [analog.model_dump()],
        "risk": {"summary": "риск высокий"},
        "steps_done": ["parser", "timeline", "retriever", "risk"],
    }
    result = respond_node(state)
    answer = result["final_answer"]
    assert "02-0001/2024" in answer
    assert "02-0002/2024" in answer
    assert "r1" in answer
    # respond-агент выводит case_number аналога, а не case_id
    assert analog.case_number in answer
    assert "105" in answer


def test_guard_node_catches_bad_reference(tmp_path: Path, monkeypatch):
    store = _temp_store(tmp_path)
    case = _case("g1", "105", "Москва", "Первая инстанция", "Иванов", "фабула")
    store.upsert(case)

    monkeypatch.setattr(guard, "store", lambda: store)
    draft = DraftDocument(
        title="Позиция",
        body="См. дело g1 и дело 0000000000.",
        cited_case_ids=["g1", "0000000000"],
    )
    state = {"plan": ["guard"], "draft": draft.model_dump()}
    result = guard_node(state)
    assert result["guard"]["ok"] is False
    assert any("0000000000" in issue for issue in result["guard"]["issues"])
    assert "g1" in result["guard"]["verified_case_ids"]


def test_risk_node_warns_about_limited_data():
    analogs = [
        AnalogCase(case_id="x", case_number="n1", score=1.0, article="105", card_result="Вынесен ПРИГОВОР"),
        AnalogCase(case_id="y", case_number="n2", score=0.9, article="105", card_result="Вынесен ПРИГОВОР"),
    ]
    state = {
        "plan": ["risk"],
        "analogs": [a.model_dump() for a in analogs],
        "query": "оцени риск",
    }
    result = risk_node(state)
    risk = result["risk"]
    caveats = " ".join(risk["caveats"])
    assert "это распределение по загруженному срезу корпуса" in caveats
    assert "оправдательных в базе почти нет" in caveats
    assert len(analogs) < 8
    assert "мало аналогов" in caveats
