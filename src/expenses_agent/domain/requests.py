from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator

from expenses_agent.domain.expenses import PaidBy


def normalize_us_phone(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) == 10:
        digits = f"1{digits}"
    if len(digits) != 11 or not digits.startswith("1"):
        raise ValueError("expected a US phone number")
    return f"+{digits}"


class AgentAction(StrEnum):
    WRITE = "write"
    READ = "read"


class InboundSMS(BaseModel):
    message_sid: str = Field(min_length=1)
    from_number: str
    to_number: str
    body: str = Field(min_length=1)
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(ZoneInfo("America/Los_Angeles"))
    )

    @field_validator("from_number", "to_number")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return normalize_us_phone(value)


class AgentRequest(BaseModel):
    schema_version: str = "1.0"
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    action: AgentAction
    sms: InboundSMS
    default_payer: PaidBy | None = None
    prior_results: list[str] = Field(default_factory=list)
