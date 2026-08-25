from __future__ import annotations

import re
from typing import Any

from legal_multiagent.etl.fields import extract_articles_from_text
from legal_multiagent.models import CaseGraph, Charge, JudicialAct

_CASE_NUM_RE = re.compile(
    r"дело\s*№\s*([0-9]{1,2}\s*-\s*[0-9]+(?:\s*/\s*[0-9]{2,4})?)",
    re.IGNORECASE,
)
_JUDGE_RE = re.compile(
    r"судьи?\s+([а-яё]{2,}(?:\s+[а-яё]\.){0,2})",
    re.IGNORECASE,
)
_COURT_RE = re.compile(
    r"((?:[а-яё]+[-\s]+){0,5}(?:районный|городской|областной|краевой|верховный|мировой|арбитражный)\s+суд(?:\s+[а-яё\-\s]{0,30})?)",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"\b(20[0-2]\d)\b")
_MONTHS = {
    "января": "01",
    "февраля": "02",
    "марта": "03",
    "апреля": "04",
    "мая": "05",
    "июня": "06",
    "июля": "07",
    "августа": "08",
    "сентября": "09",
    "октября": "10",
    "ноября": "11",
    "декабря": "12",
}


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def detect_kind(header: str) -> str:
    text = header.lower()
    if re.search(r"уголовн\w+\s+дело", text) and "возмещен" not in text:
        return "Уголовное дело"
    if "административн" in text:
        return "Административное дело"
    if "гражданск" in text or re.search(r"дело\s*№\s*2-", text):
        return "Гражданское дело"
    return "Не определен"


def detect_instance(header: str) -> str:
    text = header.lower()
    if "апелляц" in text or re.search(r"дело\s*№\s*33-", text):
        return "Апелляция"
    if "кассац" in text:
        return "Кассация"
    return "Первая инстанция"


def extract_case_number(header: str) -> str:
    match = _CASE_NUM_RE.search(header)
    if not match:
        return ""
    return re.sub(r"\s+", "", match.group(1))


def extract_judge(header: str) -> str:
    match = _JUDGE_RE.search(header)
    return _clean(match.group(1)) if match else ""


def extract_court(header: str) -> str:
    match = _COURT_RE.search(header)
    return _clean(match.group(1)) if match else ""


def extract_year(header: str) -> int | None:
    match = _YEAR_RE.search(header)
    return int(match.group(1)) if match else None


def extract_result(resolutive: str) -> str:
    text = resolutive.lower()
    rules = [
        (r"отказать", "В иске отказано"),
        (r"удовлетворить\s+частично|частично\s+удовлетворить", "Иск удовлетворён частично"),
        (r"удовлетворить", "Иск удовлетворён"),
        (r"взыскать", "Взыскание"),
        (r"прекратить", "Производство прекращено"),
        (r"оправд", "Оправдательный приговор"),
        (r"признать\s+виновн|приговор", "Обвинительный приговор"),
        (r"оставить\s+без\s+изменен", "Оставлено без изменения"),
        (r"отменить", "Акт отменён"),
    ]
    for pattern, label in rules:
        if re.search(pattern, text):
            return label
    return ""


def parquet_row_to_case(row: dict[str, Any]) -> CaseGraph:
    header = _clean(row.get("text_1"))
    fabula = _clean(row.get("text_2"))
    resolutive = _clean(row.get("text_3"))
    record_id = str(row.get("id") or "").strip()
    kind = detect_kind(header)
    charges: list[Charge] = []
    seen: set[str] = set()
    blob = f"{header} {fabula} {resolutive}"
    if re.search(r"\b(?:ук|коап|гк|гпк|нк)\b", blob, re.IGNORECASE):
        for parsed in extract_articles_from_text(blob):
            key = parsed["canonical"]
            if not key or key in seen or not parsed["article"]:
                continue
            if parsed["article"] in {"1", "2", "3"}:
                continue
            seen.add(key)
            charges.append(Charge(**parsed, source="act_text"))

    joined = " ".join(part for part in (header, fabula, resolutive) if part)
    gaps: list[str] = []
    if not fabula:
        gaps.append("нет фабулы (text_2)")
    if not resolutive:
        gaps.append("нет резолютивки (text_3)")

    return CaseGraph(
        record_id=record_id,
        case_id=record_id,
        case_number=extract_case_number(header),
        name=header[:180],
        source="parquet",
        year=extract_year(header),
        instance=detect_instance(header),
        case_type=kind,
        kind=kind,
        court=extract_court(header),
        judge=extract_judge(header),
        card_result=extract_result(resolutive),
        document_result=extract_result(resolutive),
        charges=charges[:8],
        act=JudicialAct(
            document_id=record_id,
            doc_type="Решение" if "решение" in header.lower() else "",
            result=extract_result(resolutive),
            has_text=bool(joined),
            text=joined[:80000],
            text_chars=len(joined),
        ),
        split_header=header[:4000],
        split_fabula=fabula[:8000],
        split_resolutive=resolutive[:4000],
        gaps=gaps,
    )
