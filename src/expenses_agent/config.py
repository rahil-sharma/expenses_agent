from __future__ import annotations

from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AliasChoices, Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from expenses_agent.domain.expenses import PaidBy
from expenses_agent.domain.requests import normalize_us_phone


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    app_env: str = "development"
    log_level: str = "INFO"
    timezone: str = "America/Los_Angeles"
    model_backend: Literal["stub", "anthropic"] = "stub"
    sheets_backend: Literal["fake", "google"] = "fake"

    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-sonnet-4-5"
    supervisor_prompt_id: str | None = None
    read_agent_prompt_id: str | None = None
    write_agent_prompt_id: str | None = None

    twilio_account_sid: str | None = Field(
        default=None, validation_alias=AliasChoices("TWILIO_ACCOUNT_SID", "TWILIO_SID")
    )
    twilio_auth_token: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("TWILIO_AUTH_TOKEN", "TWILIO_CLIENT_SECRET")
    )
    twilio_validate_signatures: bool = True
    authorized_sender_rahil: str | None = None
    authorized_sender_karishma: str | None = None

    google_application_credentials: str | None = None
    google_sheets_spreadsheet_id: str | None = None

    read_agent_url: HttpUrl = HttpUrl("http://127.0.0.1:8001")
    write_agent_url: HttpUrl = HttpUrl("http://127.0.0.1:8002")
    a2a_timeout_seconds: float = 12.0

    @property
    def zoneinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def sender_payer_map(self) -> dict[str, PaidBy]:
        pairs = (
            (self.authorized_sender_rahil, PaidBy.RAHIL),
            (self.authorized_sender_karishma, PaidBy.KARISHMA),
        )
        return {normalize_us_phone(number): payer for number, payer in pairs if number}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
