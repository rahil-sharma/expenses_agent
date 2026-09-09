from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from expenses_agent.domain import AgentRequest, AgentResult, ExpenseQuery, SheetRecord


class ReadAgentState(BaseModel):
    request: AgentRequest
    query: ExpenseQuery | None = None
    aggregation: Literal["total", "by_category", "by_payer", "list"] = "total"
    matches: list[SheetRecord] = Field(default_factory=list)
    summary: dict[str, str] = Field(default_factory=dict)
    result: AgentResult | None = None
    errors: list[str] = Field(default_factory=list)


class ParsedReadIntent(BaseModel):
    query: ExpenseQuery
    aggregation: Literal["total", "by_category", "by_payer", "list"] = "total"
