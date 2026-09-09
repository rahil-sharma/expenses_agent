from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ResultStatus(StrEnum):
    SUCCESS = "success"
    CLARIFICATION = "clarification"
    NOT_FOUND = "not_found"
    ERROR = "error"


class AgentResult(BaseModel):
    schema_version: str = "1.0"
    status: ResultStatus
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
