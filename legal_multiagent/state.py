from __future__ import annotations

import operator
from typing import Annotated, Any, Optional, TypedDict


class AgentState(TypedDict, total=False):
    query: str
    playbook: str
    plan: list[str]
    case_id: Optional[str]
    case_number: Optional[str]
    query_article: str
    case: dict[str, Any]
    timeline: dict[str, Any]
    act_brief: dict[str, Any]
    qualification: dict[str, Any]
    analogs: list[dict[str, Any]]
    risk: dict[str, Any]
    appeal: dict[str, Any]
    draft: dict[str, Any]
    guard: dict[str, Any]
    final_answer: str
    llm_used: bool
    steps_done: Annotated[list[str], operator.add]
    gaps: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]
