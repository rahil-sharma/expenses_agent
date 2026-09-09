from __future__ import annotations

from typing import Any, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from expenses_agent.agents.common.prompt_loader import build_chat_model, load_prompt_text
from expenses_agent.config import Settings, get_settings
from expenses_agent.domain import AgentAction, AgentRequest, AgentResult, ResultStatus
from expenses_agent.orchestrator.a2a_clients import A2AAgentClient, AgentClient
from expenses_agent.orchestrator.prompts import SUPERVISOR_PROMPT
from expenses_agent.orchestrator.state import SupervisorPlan, SupervisorState


def _stub_route(text: str) -> SupervisorPlan:
    lowered = text.casefold()
    write_terms = ("spent", "bought", "purchase", "add", "log", "mark", "update", "settle")
    read_terms = (
        "how much",
        "total",
        "summary",
        "summarize",
        "list",
        "show",
        "find",
        "charge",
        "unsettled",
    )
    has_write = any(term in lowered for term in write_terms)
    has_read = any(term in lowered for term in read_terms)
    actions = []
    if has_write:
        actions.append(AgentAction.WRITE)
    if has_read:
        actions.append(AgentAction.READ)
    if not actions and any(character.isdigit() for character in text):
        actions.append(AgentAction.WRITE)
    return SupervisorPlan(
        actions=actions,
        clarification=None if actions else "Are you adding an expense or asking about expenses?",
    )


def build_supervisor_graph(
    *,
    settings: Settings | None = None,
    read_client: AgentClient | None = None,
    write_client: AgentClient | None = None,
    model: BaseChatModel | None = None,
) -> Any:
    resolved_settings = settings or get_settings()
    resolved_read_client = read_client or A2AAgentClient(
        str(resolved_settings.read_agent_url), resolved_settings.a2a_timeout_seconds
    )
    resolved_write_client = write_client or A2AAgentClient(
        str(resolved_settings.write_agent_url), resolved_settings.a2a_timeout_seconds
    )
    resolved_model = model if model is not None else build_chat_model(resolved_settings)

    async def route(state: SupervisorState) -> dict[str, object]:
        if resolved_model is None:
            plan = _stub_route(state.sms.body)
        else:
            prompt = load_prompt_text(resolved_settings.supervisor_prompt_id, SUPERVISOR_PROMPT)
            structured = resolved_model.with_structured_output(SupervisorPlan)
            plan = cast(
                SupervisorPlan,
                await structured.ainvoke(
                    [
                        SystemMessage(content=prompt),
                        HumanMessage(content=state.sms.model_dump_json()),
                    ]
                ),
            )
        ordered = [
            action for action in (AgentAction.WRITE, AgentAction.READ) if action in plan.actions
        ]
        return {"actions": ordered, "clarification": plan.clarification}

    async def call_write(state: SupervisorState) -> dict[str, object]:
        if AgentAction.WRITE not in state.actions:
            return {}
        request = AgentRequest(
            action=AgentAction.WRITE,
            sms=state.sms,
            default_payer=state.default_payer.value,
            prior_results=[result.message for result in state.results],
        )
        try:
            result = await resolved_write_client.call(request)
            return {"results": [*state.results, result]}
        except Exception as error:
            result = AgentResult(status=ResultStatus.ERROR, message=f"Write agent error: {error}")
            return {"results": [*state.results, result], "errors": [*state.errors, str(error)]}

    async def call_read(state: SupervisorState) -> dict[str, object]:
        if AgentAction.READ not in state.actions:
            return {}
        request = AgentRequest(
            action=AgentAction.READ,
            sms=state.sms,
            default_payer=state.default_payer.value,
            prior_results=[result.message for result in state.results],
        )
        try:
            result = await resolved_read_client.call(request)
            return {"results": [*state.results, result]}
        except Exception as error:
            result = AgentResult(status=ResultStatus.ERROR, message=f"Read agent error: {error}")
            return {"results": [*state.results, result], "errors": [*state.errors, str(error)]}

    async def respond(state: SupervisorState) -> dict[str, object]:
        if state.results:
            return {"response_text": " ".join(result.message for result in state.results)}
        return {
            "response_text": state.clarification
            or "I couldn't determine whether to read or write an expense."
        }

    builder = StateGraph(SupervisorState)
    builder.add_node("supervisor", route)
    builder.add_node("write_agent_a2a", call_write)
    builder.add_node("read_agent_a2a", call_read)
    builder.add_node("respond", respond)
    builder.add_edge(START, "supervisor")
    builder.add_edge("supervisor", "write_agent_a2a")
    builder.add_edge("write_agent_a2a", "read_agent_a2a")
    builder.add_edge("read_agent_a2a", "respond")
    builder.add_edge("respond", END)
    return builder.compile()


graph = build_supervisor_graph()
