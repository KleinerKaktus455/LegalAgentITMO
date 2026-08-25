from __future__ import annotations

import json
from pathlib import Path

import pytest

from legal_multiagent.agents.respond import _render_analogs_table
from legal_multiagent.etl.fields import overlap_score, parse_article
from legal_multiagent.models import AnalogCase, CaseGraph, Charge
from legal_multiagent.store.sqlite_store import CaseStore
from legal_multiagent.ui_helpers import _format_analogs, _format_number, _split_analogs_section


def test_parse_card_article():
    parsed = parse_article("Статья 158 Часть 2 п. в")
    assert parsed["article"] == "158"
    assert parsed["part"] == "2"
    assert parsed["canonical"].startswith("158")


def test_overlap_score_range_and_ranking():
    similar = overlap_score("взыскание налоговой недоимки", "налоговая недоимка взыскание")
    different = overlap_score("взыскание налоговой недоимки", "преступление по статье 105")
    assert 0 <= similar <= 1
    assert 0 <= different <= 1
    assert similar > different


def _make_case(
    case_id: str,
    article_num: str,
    region: str,
    instance: str,
    judge: str,
    fabula: str,
) -> CaseGraph:
    return CaseGraph(
        case_id=case_id,
        case_number=f"{case_id}-num",
        article=article_num,
        region=region,
        instance=instance,
        judge=judge,
        source="test",
        split_fabula=fabula,
        charges=[Charge(article=article_num, canonical=article_num)],
    )


def _temp_store(tmp_path: Path) -> CaseStore:
    return CaseStore(path=tmp_path / "test.sqlite")


def test_search_analogs_score_normalized(tmp_path: Path):
    store = _temp_store(tmp_path)
    cases = [
        _make_case("c1", "105", "Москва", "Первая инстанция", "Иванов", "убийство ревность нож"),
        _make_case("c2", "105", "Москва", "Первая инстанция", "Петров", "убийство ссора нож"),
        _make_case("c3", "105", "СПб", "Первая инстанция", "Сидоров", "убийство дорога"),
        _make_case("c4", "158", "Москва", "Первая инстанция", "Иванов", "кража кошелек"),
    ]
    for c in cases:
        store.upsert(c)

    analogs = store.search_analogs(
        article_num="105",
        region="Москва",
        instance="Первая инстанция",
        judge="Иванов",
        query_text="убийство ревность нож",
        exclude_id="c1",
        limit=20,
    )

    assert len(analogs) > 0
    scores = [a.score for a in analogs]
    assert all(0 <= s <= 1 for s in scores)
    assert scores[0] == 1.0
    assert scores == sorted(scores, reverse=True)

    ids = [a.case_id for a in analogs]
    assert "c1" not in ids
    assert "c2" in ids


def test_search_analogs_empty_returns_empty(tmp_path: Path):
    store = _temp_store(tmp_path)
    analogs = store.search_analogs(
        article_num="999",
        region="НетТакого",
        query_text="абракадабра",
    )
    assert analogs == []


def test_format_number():
    assert _format_number(1218400) == "1.218.400"
    assert _format_number(0) == "0"
    assert _format_number(123) == "123"
    assert _format_number(1234567890) == "1.234.567.890"


def test_render_analogs_table():
    analogs = [
        {
            "case_number": "02-0001/2024",
            "case_id": "abc",
            "article": "ст. 105",
            "document_result": "осуждение",
            "score": 0.912,
            "reasons": ["статья", "регион"],
        },
        {
            "case_number": "",
            "case_id": "def",
            "article": "",
            "document_result": "",
            "score": None,
            "reasons": [],
        },
    ]
    table = _render_analogs_table(analogs)
    assert table.startswith("| № дела | Статья | Исход | Score | Причины |")
    assert "02-0001/2024" in table
    assert "0.912" in table
    assert "def" in table
    assert table.count("|") >= 6


def test_split_analogs_section_found():
    text = "## Досье\nТекст\n\n## Аналоги\nтаблица\n\n## Оценка практики\nстатистика"
    split = _split_analogs_section(text)
    assert split is not None
    before, after = split
    assert "## Досье" in before
    assert "## Аналоги" not in before
    assert "## Оценка практики" in after


def test_split_analogs_section_not_found():
    assert _split_analogs_section("## Досье\nТекст") is None


def test_format_analogs():
    rows = _format_analogs(
        [
            {
                "case_number": "02-0001/2024",
                "case_id": "abc",
                "article": "ст. 105",
                "document_result": "осуждение",
                "region": "Москва",
                "judge": "Иванов",
                "score": 0.912,
                "reasons": ["статья", "регион"],
            },
            {
                "case_number": "",
                "case_id": "def",
                "article": None,
                "document_result": None,
                "region": None,
                "judge": None,
                "score": None,
                "reasons": None,
            },
        ]
    )
    assert len(rows) == 2
    assert rows[0]["Score"] == 0.912
    assert rows[1]["Статья"] == "—"
    assert rows[1]["Причины"] == "—"


def test_analog_case_model_dump_roundtrip():
    a = AnalogCase(
        case_id="x",
        case_number="1-1/2024",
        score=0.75,
        reasons=["статья"],
        article="105",
    )
    data = a.model_dump()
    restored = AnalogCase.model_validate(data)
    assert restored.score == 0.75
    assert restored.reasons == ["статья"]


@pytest.mark.skipif(not list(Path("data/correct_df_splitted_text.parquet").glob("*.parquet")), reason="parquet data not present")
def test_ingest_parquet_limit(tmp_path: Path):
    from legal_multiagent.etl.ingest import ingest

    stats = ingest(
        source="parquet",
        limit=10,
        reset=True,
        parquet_root=Path("data/correct_df_splitted_text.parquet"),
    )
    assert stats["written"] == 10


def test_ingest_no_data_raises(tmp_path: Path):
    from legal_multiagent.etl.ingest import ingest

    with pytest.raises(FileNotFoundError):
        ingest(
            source="both",
            limit=10,
            reset=True,
            parquet_root=tmp_path / "empty_parquet",
            docs_dir=tmp_path / "empty_docs",
        )
