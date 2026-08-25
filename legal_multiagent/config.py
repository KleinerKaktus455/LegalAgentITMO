from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_DIR / "data"

load_dotenv(REPO_ROOT / ".env")
load_dotenv(PACKAGE_DIR / ".env")


def docs_json_dir() -> Path:
    raw = os.getenv("DOCS_JSON_DIR", str(REPO_ROOT / "docs.json"))
    return Path(raw).expanduser().resolve()


def parquet_dir() -> Path:
    raw = os.getenv(
        "PARQUET_DIR",
        str(REPO_ROOT / "data" / "correct_df_splitted_text.parquet"),
    )
    return Path(raw).expanduser().resolve()


def store_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    raw = os.getenv("CASE_STORE_PATH", str(DATA_DIR / "case_store.sqlite"))
    path = Path(raw).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def ollama_api_key() -> str:
    return os.getenv("OLLAMA_API_KEY", "").strip()


def ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "https://ollama.com/v1").rstrip("/")


def ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "gpt-oss:20b")


def default_ingest_limit() -> int:
    return int(os.getenv("INGEST_LIMIT", "2000"))
