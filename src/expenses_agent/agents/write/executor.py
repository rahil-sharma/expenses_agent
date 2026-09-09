from __future__ import annotations

from expenses_agent.agents.common.a2a import GraphAgentExecutor
from expenses_agent.agents.write.graph import graph
from expenses_agent.agents.write.state import WriteAgentState
from expenses_agent.domain import AgentRequest, AgentResult, ResultStatus


async def run_write_graph(request: AgentRequest) -> AgentResult:
    output = await graph.ainvoke({"request": request})
    state = WriteAgentState.model_validate(output)
    return state.result or AgentResult(
        status=ResultStatus.ERROR, message="Write graph returned no result."
    )


def build_executor() -> GraphAgentExecutor:
    return GraphAgentExecutor(run_write_graph)
