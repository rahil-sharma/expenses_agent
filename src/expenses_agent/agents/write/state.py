from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from expenses_agent.domain import (
    AgentRequest,
    AgentResult,
    ExpensePatch,
    ExpenseQuery,
    ExpenseRow,
    SheetRecord,
)


class WriteAgentState(BaseModel):
    request: AgentRequest
    operation: Literal["add", "update", "clarify"] | None = None
    expense: ExpenseRow | None = None
    query: ExpenseQuery | None = None
    patch: ExpensePatch | None = None
    candidates: list[SheetRecord] = Field(default_factory=list)
    result: AgentResult | None = None
    errors: list[str] = Field(default_factory=list)


class ParsedWriteIntent(BaseModel):
    operation: Literal["add", "update", "clarify"]
    expense: ExpenseRow | None = None
    query: ExpenseQuery | None = None
    patch: ExpensePatch | None = None
    clarification: str | None = None
