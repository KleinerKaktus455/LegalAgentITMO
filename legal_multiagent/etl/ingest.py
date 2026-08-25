from __future__ import annotations

import json
from pathlib import Path

from legal_multiagent.config import default_ingest_limit, docs_json_dir, parquet_dir
from legal_multiagent.etl.normalize import record_to_case
from legal_multiagent.etl.parquet_normalize import parquet_row_to_case
from legal_multiagent.store.sqlite_store import CaseStore


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def discover_shards(docs_dir: Path | None = None) -> list[Path]:
    root = docs_dir or docs_json_dir()
    if not root.exists():
        return []
    files = sorted(root.glob("*docs.json"))
    if not files:
        files = sorted(root.glob("*.json"))
    return files


def discover_parquet_parts(root: Path | None = None) -> list[Path]:
    directory = root or parquet_dir()
    if directory.is_file() and directory.suffix == ".parquet":
        return [directory]
    if not directory.exists():
        return []
    return sorted(
        p
        for p in directory.glob("*.parquet")
        if p.is_file() and not p.name.startswith(".")
    )


def _ingest_docs(store: CaseStore, cap: int, written: int, docs_dir: Path | None) -> tuple[int, int, int]:
    skipped = 0
    shards = discover_shards(docs_dir)
    for shard in shards:
        for record in iter_jsonl(shard):
            if cap and written >= cap:
                return written, skipped, len(shards)
            try:
                case = record_to_case(record)
            except Exception:
                skipped += 1
                continue
            if not case.case_id and not case.case_number:
                skipped += 1
                continue
            existing = store.get(case.case_id or case.record_id) or store.get(case.record_id)
            if existing and existing.split_fabula and not case.split_fabula:
                case.split_header = existing.split_header
                case.split_fabula = existing.split_fabula
                case.split_resolutive = existing.split_resolutive
            store.upsert(case)
            written += 1
    return written, skipped, len(shards)


def _ingest_parquet(store: CaseStore, cap: int, written: int, parquet_root: Path | None) -> tuple[int, int, int]:
    import pyarrow.parquet as pq

    skipped = 0
    parts = discover_parquet_parts(parquet_root)
    for part in parts:
        table = pq.read_table(part)
        for row in table.to_pylist():
            if cap and written >= cap:
                return written, skipped, len(parts)
            try:
                case = parquet_row_to_case(row)
            except Exception:
                skipped += 1
                continue
            if not case.case_id:
                skipped += 1
                continue
            existing = store.get(case.case_id)
            if existing and existing.source == "docs.json":
                existing.split_header = case.split_header
                existing.split_fabula = case.split_fabula
                existing.split_resolutive = case.split_resolutive
                if case.act and case.act.has_text and (not existing.act or not existing.act.has_text):
                    existing.act = case.act
                store.upsert(existing)
            else:
                store.upsert(case)
            written += 1
    return written, skipped, len(parts)


def ingest(
    limit: int | None = None,
    docs_dir: Path | None = None,
    parquet_root: Path | None = None,
    reset: bool = False,
    source: str = "both",
) -> dict[str, int]:
    store = CaseStore()
    if reset:
        store.reset()

    cap = default_ingest_limit() if limit is None else limit
    written = 0
    skipped = 0
    docs_shards = 0
    parquet_parts = 0

    if source in {"parquet", "both"}:
        written, skip_p, parquet_parts = _ingest_parquet(store, cap, written, parquet_root)
        skipped += skip_p
    if source in {"docs", "both"}:
        written, skip_d, docs_shards = _ingest_docs(store, cap, written, docs_dir)
        skipped += skip_d

    if written == 0 and skipped == 0:
        raise FileNotFoundError(
            "Нет данных: проверьте docs.json/ и data/correct_df_splitted_text.parquet/"
        )
    return {
        "written": written,
        "skipped": skipped,
        "docs_shards": docs_shards,
        "parquet_parts": parquet_parts,
        "source": source,
    }
