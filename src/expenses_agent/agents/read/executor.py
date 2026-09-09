from __future__ import annotations

from expenses_agent.agents.common.a2a import GraphAgentExecutor
from expenses_agent.agents.read.graph import graph
from expenses_agent.agents.read.state import ReadAgentState
from expenses_agent.domain import AgentRequest, AgentResult, ResultStatus


async def run_read_graph(request: AgentRequest) -> AgentResult:
    output = await graph.ainvoke({"request": request})
    state = ReadAgentState.model_validate(output)
    return state.result or AgentResult(
        status=ResultStatus.ERROR, message="Read graph returned no result."
    )


def build_executor() -> GraphAgentExecutor:
    return GraphAgentExecutor(run_read_graph)
