from __future__ import annotations

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langsmith import Client

from expenses_agent.config import Settings


def build_chat_model(settings: Settings) -> BaseChatModel | None:
    if settings.model_backend == "stub":
        return None
    if settings.anthropic_api_key is None:
        raise ValueError("ANTHROPIC_API_KEY is required when MODEL_BACKEND=anthropic")
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key.get_secret_value(),
        temperature=0,
    )


def load_prompt_text(prompt_id: str | None, fallback: str) -> str:
    """Load a LangSmith prompt when configured while preserving an offline fallback."""
    if not prompt_id:
        return fallback
    prompt: Any = Client().pull_prompt(prompt_id)
    if hasattr(prompt, "messages"):
        return "\n".join(str(message.prompt.template) for message in prompt.messages)
    if hasattr(prompt, "template"):
        return str(prompt.template)
    return str(prompt)
