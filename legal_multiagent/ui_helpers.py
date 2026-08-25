from __future__ import annotations

from typing import Any


def _format_number(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _format_analogs(analogs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for a in analogs:
        rows.append(
            {
                "№ дела": a.get("case_number") or a.get("case_id"),
                "id": a.get("case_id"),
                "Статья": a.get("article") or "—",
                "Исход": a.get("document_result") or a.get("card_result") or "—",
                "Регион": a.get("region") or "—",
                "Судья": a.get("judge") or "—",
                "Score": a.get("score"),
                "Причины": ", ".join(a.get("reasons") or []) or "—",
            }
        )
    return rows


def _split_analogs_section(text: str) -> tuple[str, str] | None:
    """Разделяет финальный ответ на часть до и после блока с аналогами.

    Возвращает None, если секция ## Аналоги не найдена.
    """
    marker = "## Аналоги"
    idx = text.find(marker)
    if idx == -1:
        return None
    before = text[:idx].rstrip()
    rest = text[idx + len(marker):]
    next_idx = rest.find("\n## ")
    if next_idx != -1:
        after = rest[next_idx + 1:].lstrip()
    else:
        after = ""
    return before, after
