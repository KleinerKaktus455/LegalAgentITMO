from __future__ import annotations

import re
from collections import defaultdict
from html.parser import HTMLParser
from typing import Any, Optional


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)


def html_to_text(raw: str) -> str:
    if not raw:
        return ""
    parser = _HTMLText()
    try:
        parser.feed(raw)
        text = " ".join(parser.parts)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def field_map(record: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    mapped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for field in record.get("fields") or []:
        name = field.get("name")
        if name:
            mapped[name].append(field)
    return mapped


def field_value(field: Optional[dict[str, Any]]) -> str:
    if not field:
        return ""
    for key in ("value", "dateValue", "longValue"):
        value = field.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def first_value(mapped: dict[str, list[dict[str, Any]]], *names: str) -> str:
    for name in names:
        items = mapped.get(name) or []
        if not items:
            continue
        value = field_value(items[0])
        if value:
            return value
    return ""


def all_values(mapped: dict[str, list[dict[str, Any]]], name: str) -> list[str]:
    values: list[str] = []
    for field in mapped.get(name) or []:
        value = field_value(field)
        if value:
            values.append(value)
    return values


def all_table_cols(mapped: dict[str, list[dict[str, Any]]], name: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for field in mapped.get(name) or []:
        cols = field.get("tableCols")
        if isinstance(cols, list):
            rows.append([str(c).strip() if c is not None else "" for c in cols])
    return rows


PUNISHMENT_ARTICLES = {"69", "70", "71", "72", "73", "74", "79", "80"}
PROCESS_ARTICLES = {"15", "25", "27", "76", "86"}  # тяжесть, прекращение, судимость — не состав

_ARTICLE_RE = re.compile(
    r"(?:ст(?:атья)?\.?\s*)(?P<article>\d+(?:\.\d+)?)"
    r"(?:\s*(?:ч(?:асть)?\.?\s*)(?P<part>\d+))?"
    r"(?:\s*(?:п(?:ункт)?\.?\s*[«\"']?(?P<point>[а-яёa-z0-9,\s]+)[»\"']?))?",
    re.IGNORECASE,
)

_CARD_ARTICLE_RE = re.compile(
    r"Статья\s+(?P<article>\d+(?:\.\d+)?)"
    r"(?:\s+Часть\s+(?P<part>\d+))?"
    r"(?:\s*п\.?\s*(?P<point>[а-яёa-z0-9,\s«»\"']+))?",
    re.IGNORECASE,
)


def parse_article(raw: str) -> dict[str, str]:
    text = (raw or "").strip()
    if not text:
        return {"raw": "", "article": "", "part": "", "point": "", "canonical": ""}

    match = _CARD_ARTICLE_RE.search(text) or _ARTICLE_RE.search(text)
    if not match:
        return {"raw": text, "article": "", "part": "", "point": "", "canonical": text}

    article = (match.group("article") or "").strip()
    part = (match.group("part") or "").strip()
    point = re.sub(r"\s+", "", (match.group("point") or "").strip(" .,"))
    point = point.replace("«", "").replace("»", "").replace('"', "")
    bits = [article]
    if part:
        bits.append(f"ч.{part}")
    if point:
        bits.append(f"п.{point}")
    canonical = " ".join(bits)
    return {
        "raw": text,
        "article": article,
        "part": part,
        "point": point,
        "canonical": canonical,
    }


def extract_articles_from_text(text: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in list(_CARD_ARTICLE_RE.finditer(text or "")) + list(_ARTICLE_RE.finditer(text or "")):
        parsed = parse_article(match.group(0))
        key = parsed["canonical"]
        if key and key not in seen:
            seen.add(key)
            found.append(parsed)
    return found


def tokenize(text: str) -> set[str]:
    words = re.findall(r"[а-яёa-z0-9]{3,}", (text or "").lower())
    stop = {
        "что",
        "это",
        "как",
        "для",
        "или",
        "при",
        "его",
        "ее",
        "они",
        "дело",
        "суда",
        "суд",
        "статья",
        "части",
        "часть",
        "уголовное",
        "российской",
        "федерации",
    }
    return {w for w in words if w not in stop}


def overlap_score(left: str, right: str) -> float:
    a, b = tokenize(left), tokenize(right)
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))
