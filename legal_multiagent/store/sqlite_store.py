from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Optional

from legal_multiagent.config import store_path
from legal_multiagent.etl.fields import overlap_score
from legal_multiagent.models import AnalogCase, CaseGraph


class CaseStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    record_id TEXT,
                    case_number TEXT,
                    instance TEXT,
                    region TEXT,
                    court TEXT,
                    judge TEXT,
                    year INTEGER,
                    article TEXT,
                    article_num TEXT,
                    card_result TEXT,
                    document_result TEXT,
                    has_text INTEGER,
                    source TEXT,
                    kind TEXT,
                    fabula TEXT,
                    payload TEXT NOT NULL
                )
                """
            )
            self._ensure_columns(conn)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_number ON cases(case_number)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_article ON cases(article_num)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_judge ON cases(judge)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_region ON cases(region)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_source ON cases(source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_kind ON cases(kind)")

    def _ensure_columns(self, conn: sqlite3.Connection) -> None:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(cases)")}
        for name, decl in (
            ("source", "TEXT"),
            ("kind", "TEXT"),
            ("fabula", "TEXT"),
        ):
            if name not in existing:
                conn.execute(f"ALTER TABLE cases ADD COLUMN {name} {decl}")

    def reset(self) -> None:
        if self.path.exists():
            self.path.unlink()
        self._init()

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM cases").fetchone()
            return int(row["n"] if row else 0)

    def upsert(self, case: CaseGraph) -> None:
        primary = case.charges[0] if case.charges else None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cases (
                    case_id, record_id, case_number, instance, region, court, judge,
                    year, article, article_num, card_result, document_result, has_text,
                    source, kind, fabula, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET
                    record_id=excluded.record_id,
                    case_number=excluded.case_number,
                    instance=excluded.instance,
                    region=excluded.region,
                    court=excluded.court,
                    judge=excluded.judge,
                    year=excluded.year,
                    article=excluded.article,
                    article_num=excluded.article_num,
                    card_result=excluded.card_result,
                    document_result=excluded.document_result,
                    has_text=excluded.has_text,
                    source=excluded.source,
                    kind=excluded.kind,
                    fabula=excluded.fabula,
                    payload=excluded.payload
                """,
                (
                    case.case_id or case.record_id,
                    case.record_id,
                    case.case_number,
                    case.instance,
                    case.region,
                    case.court,
                    case.judge,
                    case.year,
                    case.primary_article(),
                    primary.article if primary else "",
                    case.card_result,
                    case.document_result,
                    1 if case.act and case.act.has_text else 0,
                    case.source,
                    case.kind,
                    case.fabula_hint()[:2000],
                    case.model_dump_json(),
                ),
            )

    def get(self, case_id: str) -> Optional[CaseGraph]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM cases WHERE case_id = ?", (case_id,)
            ).fetchone()
        if not row:
            return None
        return CaseGraph.model_validate_json(row["payload"])

    def find_by_number(self, number: str) -> list[CaseGraph]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM cases WHERE case_number LIKE ?",
                (f"%{number}%",),
            ).fetchall()
        return [CaseGraph.model_validate_json(r["payload"]) for r in rows]

    def exists(self, case_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM cases WHERE case_id = ? LIMIT 1", (case_id,)
            ).fetchone()
        return row is not None

    def get_text(self, case_id: str) -> str:
        case = self.get(case_id)
        if not case or not case.act:
            return ""
        return case.act.text or ""

    def search_analogs(
        self,
        article_num: str = "",
        instance: str = "",
        region: str = "",
        judge: str = "",
        query_text: str = "",
        exclude_id: str = "",
        limit: int = 20,
    ) -> list[AnalogCase]:
        clauses = ["1=1"]
        params: list[object] = []
        if article_num:
            clauses.append("(article_num = ? OR IFNULL(fabula, '') LIKE ?)")
            params.extend([article_num, f"%{article_num}%"])
        if exclude_id:
            clauses.append("case_id != ?")
            params.append(exclude_id)

        sql = f"SELECT * FROM cases WHERE {' AND '.join(clauses)} LIMIT 800"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            if article_num and len(rows) < 15:
                extra_sql = "SELECT * FROM cases WHERE case_id != ? LIMIT 400" if exclude_id else "SELECT * FROM cases LIMIT 400"
                extra_params: list[object] = [exclude_id] if exclude_id else []
                rows = list(rows) + list(conn.execute(extra_sql, extra_params).fetchall())

        seen_ids: set[str] = set()
        raw_scored: list[tuple[AnalogCase, float]] = []
        for row in rows:
            if row["case_id"] in seen_ids:
                continue
            seen_ids.add(row["case_id"])
            score = 0.0
            reasons: list[str] = []
            if article_num and row["article_num"] == article_num:
                score += 5
                reasons.append("та же статья")
            if instance and row["instance"] == instance:
                score += 1.5
                reasons.append("та же инстанция")
            if region and row["region"] == region:
                score += 2
                reasons.append("тот же субъект РФ")
            if judge and row["judge"] and row["judge"] == judge:
                score += 3
                reasons.append("тот же судья")
            if query_text:
                keys = row.keys()
                hint = " ".join(
                    [
                        row["article"] or "",
                        row["court"] or "",
                        row["region"] or "",
                        row["fabula"] if "fabula" in keys and row["fabula"] else "",
                    ]
                )
                if not hint.strip() or hint == (row["article"] or ""):
                    payload = json.loads(row["payload"])
                    hint = " ".join(
                        [
                            hint,
                            payload.get("split_fabula") or "",
                            (payload.get("act") or {}).get("text", "")[:1500],
                        ]
                    )
                overlap = overlap_score(query_text, hint)
                if overlap:
                    score += overlap * 6
                    reasons.append(f"похожесть фабулы {overlap:.2f}")
            if score <= 0:
                continue
            analog = AnalogCase(
                case_id=row["case_id"],
                case_number=row["case_number"] or "",
                score=score,
                reasons=reasons,
                instance=row["instance"] or "",
                region=row["region"] or "",
                court=row["court"] or "",
                judge=row["judge"] or "",
                article=row["article"] or "",
                card_result=row["card_result"] or "",
                document_result=row["document_result"] or "",
                has_text=bool(row["has_text"]),
                kind=row["kind"] if "kind" in row.keys() and row["kind"] else "",
                source=row["source"] if "source" in row.keys() and row["source"] else "",
                fabula=(row["fabula"] or "")[:280] if "fabula" in row.keys() else "",
            )
            raw_scored.append((analog, score))

        if not raw_scored:
            return []

        max_score = max(score for _, score in raw_scored)
        scored: list[AnalogCase] = []
        for analog, raw in raw_scored:
            normalized = round(raw / max_score, 3) if max_score > 0 else 0.0
            scored.append(
                AnalogCase(
                    case_id=analog.case_id,
                    case_number=analog.case_number,
                    score=normalized,
                    reasons=analog.reasons,
                    instance=analog.instance,
                    region=analog.region,
                    court=analog.court,
                    judge=analog.judge,
                    article=analog.article,
                    card_result=analog.card_result,
                    document_result=analog.document_result,
                    has_text=analog.has_text,
                    kind=analog.kind,
                    source=analog.source,
                    fabula=analog.fabula,
                )
            )
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:limit]

    def result_distribution(self, analogs: list[AnalogCase], field: str) -> dict[str, int]:
        values = [getattr(a, field) for a in analogs if getattr(a, field)]
        return dict(Counter(values))

    def judge_profile(self, judge: str) -> dict[str, object]:
        if not judge:
            return {}
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT card_result, document_result FROM cases WHERE judge = ?",
                (judge,),
            ).fetchall()
        if not rows:
            return {"judge": judge, "n": 0}
        cards = Counter(r["card_result"] for r in rows if r["card_result"])
        docs = Counter(r["document_result"] for r in rows if r["document_result"])
        return {"judge": judge, "n": len(rows), "card_result": dict(cards), "document_result": dict(docs)}

    def region_profile(self, region: str, article_num: str = "") -> dict[str, object]:
        if not region:
            return {}
        sql = "SELECT card_result, document_result FROM cases WHERE region = ?"
        params: list[object] = [region]
        if article_num:
            sql += " AND article_num = ?"
            params.append(article_num)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        if not rows:
            return {"region": region, "n": 0}
        cards = Counter(r["card_result"] for r in rows if r["card_result"])
        return {"region": region, "article_num": article_num, "n": len(rows), "card_result": dict(cards)}
