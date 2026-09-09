from __future__ import annotations

import re
from datetime import datetime
from typing import Any, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from expenses_agent.agents.common.prompt_loader import build_chat_model, load_prompt_text
from expenses_agent.agents.read.prompts import READ_PROMPT
from expenses_agent.agents.read.state import ParsedReadIntent, ReadAgentState
from expenses_agent.agents.read.tools import ReadTools
from expenses_agent.config import Settings, get_settings
from expenses_agent.domain import (
    AgentResult,
    ExpenseCategory,
    ExpenseQuery,
    PaidBy,
    ResultStatus,
    Settled,
    SheetRecord,
)
from expenses_agent.integrations.factory import build_sheets_gateway


def _stub_parse(state: ReadAgentState, settings: Settings) -> ParsedReadIntent:
    text = state.request.sms.body
    lowered = text.casefold()
    month = next(
        (
            datetime(2000, number, 1).strftime("%B")
            for number in range(1, 13)
            if datetime(2000, number, 1).strftime("%B").casefold() in lowered
        ),
        None,
    )
    if "this month" in lowered:
        month = state.request.sms.received_at.astimezone(settings.zoneinfo).strftime("%B")
    payer = next((value for value in PaidBy if value.value.casefold() in lowered), None)
    category = next((value for value in ExpenseCategory if value.value.casefold() in lowered), None)
    settled = Settled.NO if "unsettled" in lowered else None
    quoted = re.search(r"['\"](.+?)['\"]", text)
    query = ExpenseQuery(
        month=month,
        expense_contains=quoted.group(1) if quoted else None,
        paid_by=payer,
        category=category,
        settled=settled,
    )
    if "category" in lowered or "categories" in lowered:
        aggregation = "by_category"
    elif "payer" in lowered or "paid by" in lowered:
        aggregation = "by_payer"
    elif any(word in lowered for word in ("list", "show", "find", "charge")):
        aggregation = "list"
    else:
        aggregation = "total"
    return ParsedReadIntent(query=query, aggregation=aggregation)


def _format_list(records: list[SheetRecord]) -> str:
    if not records:
        return "I couldn't find any matching expenses."
    preview = records[:5]
    parts = [
        f"{record.expense.date:%m/%d} {record.expense.expense} ${record.expense.cost:.2f}"
        for record in preview
    ]
    suffix = f" (+{len(records) - 5} more)" if len(records) > 5 else ""
    return "; ".join(parts) + suffix


def build_read_graph(
    *,
    settings: Settings | None = None,
    tools: ReadTools | None = None,
    model: BaseChatModel | None = None,
) -> Any:
    resolved_settings = settings or get_settings()
    resolved_tools = tools or ReadTools(build_sheets_gateway(resolved_settings))
    resolved_model = model if model is not None else build_chat_model(resolved_settings)

    async def interpret(state: ReadAgentState) -> dict[str, object]:
        if resolved_model is None:
            parsed = _stub_parse(state, resolved_settings)
        else:
            prompt = load_prompt_text(resolved_settings.read_agent_prompt_id, READ_PROMPT)
            structured = resolved_model.with_structured_output(ParsedReadIntent)
            parsed = cast(
                ParsedReadIntent,
                await structured.ainvoke(
                    [
                        SystemMessage(content=prompt),
                        HumanMessage(content=state.request.model_dump_json()),
                    ]
                ),
            )
        return parsed.model_dump()

    async def execute(state: ReadAgentState) -> dict[str, object]:
        query = state.query or ExpenseQuery()
        matches = await resolved_tools.search_expenses(query)
        if state.aggregation == "list":
            message = _format_list(matches)
            summary: dict[str, str] = {}
        elif state.aggregation == "by_category":
            summary = resolved_tools.group_by_category(matches)
            message = "By category: " + ", ".join(
                f"{key} ${value}" for key, value in summary.items()
            )
        elif state.aggregation == "by_payer":
            summary = resolved_tools.group_by_payer(matches)
            message = "By payer: " + ", ".join(f"{key} ${value}" for key, value in summary.items())
        else:
            summary = resolved_tools.total(matches)
            subject = f" for {query.month}" if query.month else ""
            message = f"Total{subject}: ${summary['total']} across {len(matches)} expenses."
        status = ResultStatus.SUCCESS if matches else ResultStatus.NOT_FOUND
        return {
            "matches": matches,
            "summary": summary,
            "result": AgentResult(
                status=status,
                message=message,
                data={"count": len(matches), "summary": summary},
            ),
        }

    builder = StateGraph(ReadAgentState)
    builder.add_node("interpret", interpret)
    builder.add_node("execute", execute)
    builder.add_edge(START, "interpret")
    builder.add_edge("interpret", "execute")
    builder.add_edge("execute", END)
    return builder.compile()


graph = build_read_graph()
