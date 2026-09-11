from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.types import Message, Role, SendMessageRequest

from expenses_agent.agents.common.a2a import (
    GraphAgentExecutor,
    data_part_to_dict,
    dict_to_data_part,
)
from expenses_agent.agents.write.app import create_app
from expenses_agent.domain import (
    AgentAction,
    AgentRequest,
    AgentResult,
    InboundSMS,
    ResultStatus,
)


async def deterministic_runner(request: AgentRequest) -> AgentResult:
    assert request.action is AgentAction.WRITE
    return AgentResult(status=ResultStatus.SUCCESS, message="Expense accepted.")


async def test_write_agent_card_and_a2a_data_contract() -> None:
    app = create_app(
        base_url="http://agent.test", executor=GraphAgentExecutor(deterministic_runner)
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://agent.test") as http_client:
        card_response = await http_client.get("/.well-known/agent-card.json")
        assert card_response.status_code == 200
        assert card_response.json()["skills"][0]["id"] == "expenses.write"

        factory = ClientFactory(ClientConfig(streaming=False, httpx_client=http_client))
        client = await factory.create_from_url("http://agent.test")
        request = AgentRequest(
            action=AgentAction.WRITE,
            default_payer="Rahil",
            sms=InboundSMS(
                message_sid="SM-A2A",
                from_number="9802138727",
                to_number="9195550100",
                body="Log $9.50 at Coffee Shop",
                received_at=datetime(2026, 9, 9, tzinfo=ZoneInfo("America/Los_Angeles")),
            ),
        )
        message = Message(
            message_id="message-1",
            role=Role.ROLE_USER,
            parts=[dict_to_data_part(request.model_dump(mode="json"))],
        )
        responses = [
            response async for response in client.send_message(SendMessageRequest(message=message))
        ]
        response_message = next(
            response.message
            for response in responses
            if response.WhichOneof("payload") == "message"
        )
        result = AgentResult.model_validate(data_part_to_dict(response_message.parts[0]))
        assert result.status == "success"
