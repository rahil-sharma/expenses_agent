from __future__ import annotations

from pydantic import BaseModel, Field

from expenses_agent.domain import AgentAction, AgentResult, InboundSMS, PaidBy


class SupervisorState(BaseModel):
    sms: InboundSMS
    default_payer: PaidBy
    actions: list[AgentAction] = Field(default_factory=list)
    clarification: str | None = None
    results: list[AgentResult] = Field(default_factory=list)
    response_text: str | None = None
    errors: list[str] = Field(default_factory=list)


class SupervisorPlan(BaseModel):
    actions: list[AgentAction] = Field(default_factory=list)
    clarification: str | None = None
