from __future__ import annotations

import json
import re
from typing import Any, Optional

from legal_multiagent.config import ollama_api_key, ollama_base_url, ollama_model


def get_llm():
    key = ollama_api_key()
    if not key:
        return None
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None
    return ChatOpenAI(
        model=ollama_model(),
        api_key=key,
        base_url=ollama_base_url(),
        temperature=0.1,
        max_tokens=1800,
    )


def invoke_text(system: str, user: str) -> Optional[str]:
    llm = get_llm()
    if llm is None:
        return None
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        result = llm.invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        content = result.content
        if isinstance(content, list):
            return "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return str(content)
    except Exception:
        return None


def invoke_json(system: str, user: str) -> Optional[dict[str, Any]]:
    raw = invoke_text(
        system + "\nОтветь только валидным JSON без markdown.",
        user,
    )
    if not raw:
        return None
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
