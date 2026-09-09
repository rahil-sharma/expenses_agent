from datetime import datetime
from zoneinfo import ZoneInfo

from expenses_agent.agents.read.graph import build_read_graph
from expenses_agent.agents.read.state import ReadAgentState
from expenses_agent.agents.read.tools import ReadTools
from expenses_agent.agents.write.graph import build_write_graph
from expenses_agent.agents.write.state import WriteAgentState
from expenses_agent.agents.write.tools import WriteTools
from expenses_agent.config import Settings
from expenses_agent.domain import AgentAction, AgentRequest, InboundSMS, ResultStatus
from expenses_agent.integrations.fake_sheets import FakeSheetsGateway


def request(body: str, action: AgentAction) -> AgentRequest:
    return AgentRequest(
        action=action,
        default_payer="Rahil",
        sms=InboundSMS(
            message_sid=f"SM-{action}",
            from_number="9802138727",
            to_number="9195550100",
            body=body,
            received_at=datetime(2026, 9, 9, 12, tzinfo=ZoneInfo("America/Los_Angeles")),
        ),
    )


async def test_write_then_read_with_injected_shared_backend() -> None:
    settings = Settings(_env_file=None, model_backend="stub")
    sheets = FakeSheetsGateway()
    write_graph = build_write_graph(settings=settings, tools=WriteTools(sheets))
    read_graph = build_read_graph(settings=settings, tools=ReadTools(sheets))

    write_output = await write_graph.ainvoke(
        {"request": request("Log $42.18 at Trader Joe's", AgentAction.WRITE)}
    )
    write_state = WriteAgentState.model_validate(write_output)
    assert write_state.result is not None
    assert write_state.result.status is ResultStatus.SUCCESS

    read_output = await read_graph.ainvoke(
        {"request": request("How much this month?", AgentAction.READ)}
    )
    read_state = ReadAgentState.model_validate(read_output)
    assert read_state.summary == {"total": "42.18"}


async def test_ambiguous_update_does_not_write() -> None:
    settings = Settings(_env_file=None, model_backend="stub")
    sheets = FakeSheetsGateway()
    graph = build_write_graph(settings=settings, tools=WriteTools(sheets))

    output = await graph.ainvoke({"request": request("Mark something settled", AgentAction.WRITE)})
    state = WriteAgentState.model_validate(output)
    assert state.result is not None
    assert state.result.status is ResultStatus.CLARIFICATION
