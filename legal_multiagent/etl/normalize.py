from __future__ import annotations

from typing import Any

from legal_multiagent.etl.fields import (
    all_table_cols,
    all_values,
    extract_articles_from_text,
    field_map,
    first_value,
    html_to_text,
    parse_article,
)
from legal_multiagent.models import CaseGraph, Charge, Event, JudicialAct, Party


def record_to_case(record: dict[str, Any]) -> CaseGraph:
    mapped = field_map(record)
    gaps: list[str] = []

    charges: list[Charge] = []
    seen: set[str] = set()
    for raw in all_values(mapped, "u_case_user_article") + all_values(mapped, "u_case_common_article"):
        parsed = parse_article(raw)
        key = parsed["canonical"] or parsed["raw"]
        if key in seen:
            continue
        seen.add(key)
        charges.append(Charge(**parsed, source="card"))

    for raw in all_values(mapped, "case_document_articles") + all_values(
        mapped, "case_document_category_article"
    ):
        parsed = parse_article(raw)
        key = parsed["canonical"] or parsed["raw"]
        if key in seen:
            continue
        seen.add(key)
        charges.append(Charge(**parsed, source="act_meta"))

    events: list[Event] = []
    event_rows = all_table_cols(mapped, "case_common_event_m2")
    event_names = all_values(mapped, "case_common_event_name")
    event_results = all_values(mapped, "case_common_event_result")
    event_dates = all_values(mapped, "case_common_event_date")
    if event_rows:
        for idx, cols in enumerate(event_rows):
            date = cols[0] if len(cols) > 0 else ""
            time = cols[1] if len(cols) > 1 else ""
            name = cols[2] if len(cols) > 2 else ""
            result = cols[3] if len(cols) > 3 else ""
            if not name and idx < len(event_names):
                name = event_names[idx]
            if not result and idx < len(event_results):
                result = event_results[idx]
            if not date and idx < len(event_dates):
                date = event_dates[idx]
            events.append(
                Event(
                    date=date,
                    time=time,
                    name=name,
                    result=result,
                    raw=" | ".join(c for c in cols if c),
                )
            )
    else:
        for idx, name in enumerate(event_names):
            events.append(
                Event(
                    date=event_dates[idx] if idx < len(event_dates) else "",
                    name=name,
                    result=event_results[idx] if idx < len(event_results) else "",
                )
            )

    parties: list[Party] = []
    for name in all_values(mapped, "u_common_case_defendant_name"):
        parties.append(Party(name=name, role="подсудимый"))
    for raw in all_values(mapped, "u_common_case_defendant_m"):
        if raw and not any(p.raw == raw for p in parties):
            parties.append(Party(role="подсудимый", raw=raw[:500]))

    raw_html = first_value(
        mapped,
        "case_document_text",
        "case_document_text2",
        "case_user_document_text_tag",
    )
    text = html_to_text(raw_html)
    txt_flag = first_value(mapped, "txt_exist")
    has_text = bool(text) or txt_flag == "Да"
    act = JudicialAct(
        document_id=first_value(mapped, "case_document_id"),
        doc_type=first_value(mapped, "case_common_document_type", "case_user_document_type"),
        result=first_value(mapped, "case_document_result", "case_document_results"),
        result_date=first_value(mapped, "case_document_result_date"),
        has_text=bool(text),
        text=text[:80000],
        text_chars=len(text),
    )

    if act.has_text:
        for parsed in extract_articles_from_text(text[:8000]):
            key = parsed["canonical"]
            if key and key not in seen:
                seen.add(key)
                charges.append(Charge(**parsed, source="act_text"))

    if not has_text:
        gaps.append("нет текста судебного акта")
    if not parties or all(not p.name for p in parties):
        gaps.append("стороны обезличены или пусты")
    if not charges:
        gaps.append("нет статьи УК на карточке")
    if not events:
        gaps.append("нет движения дела")

    year_raw = first_value(mapped, "case_year")
    year = int(year_raw) if year_raw.isdigit() else None

    return CaseGraph(
        record_id=str(record.get("id") or ""),
        case_id=first_value(mapped, "case_id", "u_case_id"),
        case_number=first_value(
            mapped,
            "case_common_doc_number",
            "case_user_doc_number",
            "case_common_doc_number_rewrite",
        ),
        name=first_value(mapped, "name"),
        year=year,
        instance=first_value(mapped, "case_doc_instance"),
        case_type=first_value(mapped, "case_common_type", "case_user_type"),
        source="docs.json",
        kind=first_value(mapped, "case_doc_kind"),
        court=first_value(mapped, "case_common_doc_court", "case_user_doc_court"),
        court_code=first_value(mapped, "case_doc_vnkod"),
        court_level=first_value(mapped, "case_court_type", "case_court_type_cat"),
        transferred_from=first_value(mapped, "case_user_court_i", "case_common_court_i", "u2_33_case_court_i"),
        judge=first_value(mapped, "case_user_judge", "case_common_judge"),
        region=first_value(mapped, "case_doc_subject_rf"),
        district=first_value(mapped, "case_doc_district_rf"),
        entry_date=first_value(
            mapped,
            "case_common_doc_entry_date",
            "case_user_doc_entry_date",
            "case_common_entry_date",
        ),
        result_date=first_value(mapped, "case_common_doc_result_date", "case_user_doc_result_date"),
        validity_date=first_value(
            mapped,
            "case_common_doc_validity_date",
            "case_user_doc_validity_date",
        ),
        card_result=first_value(mapped, "case_common_doc_result", "case_user_doc_result"),
        document_result=act.result,
        charges=charges,
        parties=parties,
        events=events,
        act=act,
        gaps=gaps,
    )
