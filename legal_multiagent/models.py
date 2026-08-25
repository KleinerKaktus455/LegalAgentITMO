from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class Charge(BaseModel):
    raw: str = ""
    article: str = ""
    part: str = ""
    point: str = ""
    source: str = "card"
    canonical: str = ""


class Party(BaseModel):
    name: str = ""
    role: str = ""
    raw: str = ""


class Event(BaseModel):
    date: str = ""
    time: str = ""
    name: str = ""
    result: str = ""
    raw: str = ""


class JudicialAct(BaseModel):
    document_id: str = ""
    doc_type: str = ""
    result: str = ""
    result_date: str = ""
    has_text: bool = False
    text: str = ""
    text_chars: int = 0


class CaseGraph(BaseModel):
    record_id: str = ""
    case_id: str = ""
    case_number: str = ""
    name: str = ""
    source: str = ""
    year: Optional[int] = None
    instance: str = ""
    case_type: str = ""
    kind: str = ""
    court: str = ""
    court_code: str = ""
    court_level: str = ""
    transferred_from: str = ""
    judge: str = ""
    region: str = ""
    district: str = ""
    entry_date: str = ""
    result_date: str = ""
    validity_date: str = ""
    card_result: str = ""
    document_result: str = ""
    charges: list[Charge] = Field(default_factory=list)
    parties: list[Party] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    act: Optional[JudicialAct] = None
    split_header: str = ""
    split_fabula: str = ""
    split_resolutive: str = ""
    gaps: list[str] = Field(default_factory=list)

    def primary_article(self) -> str:
        if not self.charges:
            return ""
        return self.charges[0].canonical or self.charges[0].raw

    def fabula_hint(self) -> str:
        if self.split_fabula:
            return self.split_fabula[:1500]
        parts = [
            self.card_result,
            self.document_result,
            " ".join(c.canonical or c.raw for c in self.charges),
            self.court,
            self.judge,
            self.region,
            self.instance,
        ]
        if self.act and self.act.text:
            parts.append(self.act.text[:1200])
        return " ".join(p for p in parts if p)


class AnalogCase(BaseModel):
    case_id: str
    case_number: str = ""
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    instance: str = ""
    region: str = ""
    court: str = ""
    judge: str = ""
    article: str = ""
    card_result: str = ""
    document_result: str = ""
    has_text: bool = False
    kind: str = ""
    source: str = ""
    fabula: str = ""


class ActBrief(BaseModel):
    available: bool = False
    header: str = ""
    fabula: str = ""
    qualification_text: str = ""
    mitigating: str = ""
    aggravating: str = ""
    special_procedure: bool = False
    resolutive: str = ""
    quotes: list[dict[str, str]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class QualificationReport(BaseModel):
    card_charges: list[str] = Field(default_factory=list)
    act_charges: list[str] = Field(default_factory=list)
    query_charges: list[str] = Field(default_factory=list)
    mismatches: list[str] = Field(default_factory=list)
    punishment_articles: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RiskReport(BaseModel):
    analog_count: int = 0
    card_result_dist: dict[str, int] = Field(default_factory=dict)
    document_result_dist: dict[str, int] = Field(default_factory=dict)
    judge_profile: dict[str, Any] = Field(default_factory=dict)
    region_profile: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    caveats: list[str] = Field(default_factory=list)


class AppealMemo(BaseModel):
    analog_count: int = 0
    typical_fates: dict[str, int] = Field(default_factory=dict)
    summary: str = ""
    suggestions: list[str] = Field(default_factory=list)


class DraftDocument(BaseModel):
    title: str = ""
    body: str = ""
    cited_case_ids: list[str] = Field(default_factory=list)
    cited_quotes: list[str] = Field(default_factory=list)


class GuardReport(BaseModel):
    ok: bool = True
    issues: list[str] = Field(default_factory=list)
    verified_case_ids: list[str] = Field(default_factory=list)
    dropped_quotes: list[str] = Field(default_factory=list)
