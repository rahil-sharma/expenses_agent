from __future__ import annotations

from typing import Protocol
from uuid import uuid4

import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.types import Message, Role, SendMessageRequest

from expenses_agent.agents.common.a2a import data_part_to_dict, dict_to_data_part
from expenses_agent.domain import AgentRequest, AgentResult, ResultStatus


class AgentClient(Protocol):
    async def call(self, request: AgentRequest) -> AgentResult: ...


class A2AAgentClient:
    def __init__(self, base_url: str, timeout_seconds: float = 12.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def call(self, request: AgentRequest) -> AgentResult:
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as http_client:
            factory = ClientFactory(ClientConfig(streaming=False, httpx_client=http_client))
            client = await factory.create_from_url(self._base_url)
            message = Message(
                message_id=str(uuid4()),
                role=Role.ROLE_USER,
                parts=[dict_to_data_part(request.model_dump(mode="json"))],
            )
            async with client:
                async for response in client.send_message(SendMessageRequest(message=message)):
                    if response.WhichOneof("payload") != "message":
                        continue
                    for part in response.message.parts:
                        if part.WhichOneof("content") == "data":
                            return AgentResult.model_validate(data_part_to_dict(part))
        return AgentResult(status=ResultStatus.ERROR, message="Agent returned no result.")
