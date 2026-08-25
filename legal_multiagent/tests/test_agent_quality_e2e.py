from __future__ import annotations

from pathlib import Path

import pytest

from legal_multiagent import config
from legal_multiagent.models import CaseGraph, Charge, Event
from legal_multiagent.store.sqlite_store import CaseStore


def _temp_store(tmp_path: Path) -> CaseStore:
    return CaseStore(path=tmp_path / "quality_e2e.sqlite")


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
    split_header: str = "",
    split_fabula: str = "",
    split_resolutive: str = "",
) -> CaseGraph:
    return CaseGraph(
        case_id=case_id,
        case_number=f"{case_id}-num",
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
    )


langgraph = pytest.importorskip("langgraph", reason="langgraph is not installed; install legal_multiagent/requirements.txt")


@pytest.mark.slow
def test_full_graph_dossier_playbook(tmp_path: Path, monkeypatch):
    from legal_multiagent.graph import run_agent

    sqlite_path = tmp_path / "quality_e2e.sqlite"
    monkeypatch.setattr(config, "store_path", lambda: sqlite_path)
    store = CaseStore()
    case = _case(
        "graph1",
        "105",
        "Москва",
        "Первая инстанция",
        "Иванов",
        "убийство",
        events=[Event(name="Судебное заседание", result="Отложено", date="01.01.2024")],
        split_fabula="Фабула",
        split_resolutive="Резолютивка",
    )
    store.upsert(case)

    result = run_agent("разбери дело", case_id="graph1", playbook="dossier")
    steps = result.get("steps_done") or []
    assert "orchestrator:dossier" in steps
    assert "parser" in steps
    assert "timeline" in steps
    assert "act_reader:splits" in steps
    assert "qualification" in steps
    assert "respond" in steps
    assert result.get("final_answer")
    assert "graph1" in result["final_answer"]
