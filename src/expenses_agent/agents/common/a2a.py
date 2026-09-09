from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Message, Part, Role
from google.protobuf import json_format, struct_pb2

from expenses_agent.domain import AgentRequest, AgentResult, ResultStatus

GraphRunner = Callable[[AgentRequest], Awaitable[AgentResult]]


def dict_to_data_part(payload: dict[str, Any]) -> Part:
    value = struct_pb2.Value()
    json_format.ParseDict(payload, value)
    return Part(data=value, media_type="application/json")


def data_part_to_dict(part: Part) -> dict[str, Any]:
    if part.WhichOneof("content") != "data":
        raise ValueError("Expected an A2A data part")
    value = json_format.MessageToDict(part.data)
    if not isinstance(value, dict):
        raise ValueError("Expected the A2A data part to contain an object")
    return value


def request_from_message(message: Message | None) -> AgentRequest:
    if message is None:
        raise ValueError("A2A request did not contain a message")
    for part in message.parts:
        if part.WhichOneof("content") == "data":
            return AgentRequest.model_validate(data_part_to_dict(part))
    raise ValueError("A2A request did not contain a versioned data part")


def response_message(result: AgentResult, *, context_id: str | None = None) -> Message:
    return Message(
        message_id=str(uuid4()),
        context_id=context_id or "",
        role=Role.ROLE_AGENT,
        parts=[dict_to_data_part(result.model_dump(mode="json"))],
    )


class GraphAgentExecutor(AgentExecutor):
    def __init__(self, runner: GraphRunner) -> None:
        self._runner = runner

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        try:
            request = request_from_message(context.message)
            result = await self._runner(request)
        except Exception as error:
            result = AgentResult(status=ResultStatus.ERROR, message=f"Agent error: {error}")
        await event_queue.enqueue_event(response_message(result, context_id=context.context_id))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        del context, event_queue
        raise NotImplementedError("Immediate expense requests cannot be cancelled")
