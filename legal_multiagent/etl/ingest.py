from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

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


def _default_progress(done: int, total: int | None, label: str = "") -> None:
    pct = f" {100 * done / total:.1f}%" if total else ""
    count = f" {done:,}/{total:,}" if total else f" {done:,}"
    bar_len = 30
    filled = int(bar_len * done / total) if total else 0
    bar = "█" * filled + "░" * (bar_len - filled)
    sys.stderr.write(f"\r{label} [{bar}]{pct}{count}")
    sys.stderr.flush()


def _ingest_docs(
    store: CaseStore,
    cap: int,
    written: int,
    docs_dir: Path | None,
    progress: Callable[[int, int | None, str], None] | None = None,
) -> tuple[int, int, int]:
    skipped = 0
    shards = discover_shards(docs_dir)
    total_shards = len(shards)
    for shard_idx, shard in enumerate(shards, start=1):
        for record in iter_jsonl(shard):
            if cap and written >= cap:
                if progress:
                    progress(written, cap if cap else None, "docs.json")
                return written, skipped, total_shards
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
            if progress and written % 100 == 0:
                progress(written, cap if cap else None, "docs.json")
    if progress:
        progress(written, cap if cap else None, "docs.json")
    return written, skipped, total_shards


def _ingest_parquet(
    store: CaseStore,
    cap: int,
    written: int,
    parquet_root: Path | None,
    progress: Callable[[int, int | None, str], None] | None = None,
) -> tuple[int, int, int]:
    import pyarrow.parquet as pq

    skipped = 0
    parts = discover_parquet_parts(parquet_root)
    total_parts = len(parts)
    known_ids = store.case_ids()
    merge_docs = store.has_source("docs.json")
    batch: list[Any] = []
    batch_size = 500
    scanned = 0

    # Оценка общего числа строк для прогресса.
    total_rows: int | None = None
    if not cap:
        try:
            total_rows = sum(pq.read_metadata(p).num_rows for p in parts)
        except Exception:
            total_rows = None

    def flush() -> None:
        store.upsert_many(batch)
        batch.clear()

    for part_idx, part in enumerate(parts, start=1):
        table = pq.read_table(part)
        rows = table.to_pylist()
        for row in rows:
            if cap and written >= cap:
                flush()
                if progress:
                    progress(written, cap if cap else None, "parquet")
                return written, skipped, total_parts
            scanned += 1
            try:
                case = parquet_row_to_case(row)
            except Exception:
                skipped += 1
                continue
            if not case.case_id:
                skipped += 1
                continue
            if case.case_id in known_ids:
                if merge_docs:
                    existing = store.get(case.case_id)
                    if existing and existing.source == "docs.json":
                        existing.split_header = case.split_header
                        existing.split_fabula = case.split_fabula
                        existing.split_resolutive = case.split_resolutive
                        if case.act and case.act.has_text and (
                            not existing.act or not existing.act.has_text
                        ):
                            existing.act = case.act
                        store.upsert(existing)
                        written += 1
                        continue
                skipped += 1
                if progress and scanned % 2000 == 0:
                    progress(scanned, cap if cap else total_rows, "parquet")
                continue
            known_ids.add(case.case_id)
            batch.append(case)
            written += 1
            if len(batch) >= batch_size:
                flush()
            if progress and (written % 500 == 0 or scanned % 2000 == 0):
                progress(max(written, scanned), cap if cap else total_rows, "parquet")
    flush()
    if progress:
        progress(written, cap if cap else total_rows, "parquet")
    return written, skipped, total_parts


def ingest(
    limit: int | None = None,
    docs_dir: Path | None = None,
    parquet_root: Path | None = None,
    reset: bool = False,
    source: str = "both",
    progress: Callable[[int, int | None, str], None] | None = None,
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
        written, skip_p, parquet_parts = _ingest_parquet(
            store, cap, written, parquet_root, progress=progress
        )
        skipped += skip_p
    if source in {"docs", "both"}:
        written, skip_d, docs_shards = _ingest_docs(
            store, cap, written, docs_dir, progress=progress
        )
        skipped += skip_d

    if progress:
        sys.stderr.write("\n")
        sys.stderr.flush()

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
