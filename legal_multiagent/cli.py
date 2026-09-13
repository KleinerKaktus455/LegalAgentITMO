from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from legal_multiagent.config import docs_json_dir, parquet_dir, store_path
from legal_multiagent.etl.ingest import ingest
from legal_multiagent.graph import run_agent
from legal_multiagent.store.sqlite_store import CaseStore


def _cmd_ingest(args: argparse.Namespace) -> int:
    from legal_multiagent.etl.ingest import _default_progress

    stats = ingest(
        limit=args.limit,
        docs_dir=Path(args.docs_dir) if args.docs_dir else None,
        parquet_root=Path(args.parquet_dir) if args.parquet_dir else None,
        reset=args.reset,
        source=args.source,
        progress=_default_progress,
    )
    print(json.dumps(stats, ensure_ascii=False))
    print(f"индекс: {store_path()}  дел: {CaseStore().count()}")
    return 0


def _cmd_status(_: argparse.Namespace) -> int:
    store = CaseStore()
    print(f"docs.json: {docs_json_dir()}")
    print(f"parquet: {parquet_dir()}")
    print(f"store: {store_path()}")
    print(f"дел в индексе: {store.count()}")
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    store = CaseStore()
    if store.count() == 0:
        print("Индекс пуст. Сначала: python -m legal_multiagent ingest --limit 1000", file=sys.stderr)
        return 2
    result = run_agent(
        query=args.query,
        case_id=args.case_id,
        case_number=args.case_number,
        playbook=args.playbook,
    )
    if args.json:
        dump = {
            key: result.get(key)
            for key in (
                "playbook",
                "plan",
                "case_id",
                "qualification",
                "analogs",
                "risk",
                "appeal",
                "guard",
                "final_answer",
                "steps_done",
                "gaps",
            )
        }
        print(json.dumps(dump, ensure_ascii=False, indent=2, default=str))
    else:
        print(result.get("final_answer") or "пустой ответ")
        if args.verbose:
            print("\n--- шаги ---")
            print(" → ".join(result.get("steps_done") or []))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="legal_multiagent",
        description="Мультиагентная система юриста по карточкам уголовных дел СОЮ",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_p = sub.add_parser("ingest", help="загрузить docs.json и/или parquet в индекс")
    ingest_p.add_argument("--limit", type=int, default=2000, help="сколько карточек; 0 = все")
    ingest_p.add_argument("--docs-dir", default="", help="путь к docs.json")
    ingest_p.add_argument("--parquet-dir", default="", help="путь к correct_df_splitted_text.parquet")
    ingest_p.add_argument(
        "--source",
        default="both",
        choices=["parquet", "docs", "both"],
        help="parquet — сплиты text_1/2/3; docs — карточки СОЮ",
    )
    ingest_p.add_argument("--reset", action="store_true", help="пересоздать sqlite")
    ingest_p.set_defaults(func=_cmd_ingest)

    status_p = sub.add_parser("status", help="состояние индекса")
    status_p.set_defaults(func=_cmd_status)

    ask_p = sub.add_parser("ask", help="задать вопрос агенту")
    ask_p.add_argument("query", help="вопрос юриста")
    ask_p.add_argument("--case-id", default=None)
    ask_p.add_argument("--case-number", default=None)
    ask_p.add_argument(
        "--playbook",
        default=None,
        choices=["dossier", "analogs", "risk", "appeal", "draft", "full"],
    )
    ask_p.add_argument("--json", action="store_true")
    ask_p.add_argument("--verbose", action="store_true")
    ask_p.set_defaults(func=_cmd_ask)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
