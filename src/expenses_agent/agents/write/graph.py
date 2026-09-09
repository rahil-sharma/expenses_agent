from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from expenses_agent.agents.common.prompt_loader import build_chat_model, load_prompt_text
from expenses_agent.agents.write.prompts import WRITE_PROMPT
from expenses_agent.agents.write.state import ParsedWriteIntent, WriteAgentState
from expenses_agent.agents.write.tools import WriteTools
from expenses_agent.config import Settings, get_settings
from expenses_agent.domain import (
    AgentResult,
    ExpenseCategory,
    ExpensePatch,
    ExpenseQuery,
    ExpenseRow,
    PaidBy,
    ResultStatus,
    Settled,
)
from expenses_agent.integrations.factory import build_sheets_gateway


def _category_from_text(text: str) -> ExpenseCategory:
    lowered = text.casefold()
    if any(word in lowered for word in ("grocery", "groceries", "trader joe", "whole foods")):
        return ExpenseCategory.GROCERIES
    if any(word in lowered for word in ("uber", "lyft", "gas", "train", "parking")):
        return ExpenseCategory.TRANSPORTATION
    if "rent" in lowered:
        return ExpenseCategory.RENT
    if any(word in lowered for word in ("restaurant", "dinner", "lunch", "coffee", "drink")):
        return ExpenseCategory.FOOD_DRINKS
    return ExpenseCategory.MISC


def _month_from_text(text: str) -> str | None:
    lowered = text.casefold()
    for month in range(1, 13):
        name = datetime(2000, month, 1).strftime("%B")
        if name.casefold() in lowered:
            return name
    return None


def _stub_parse(state: WriteAgentState, settings: Settings) -> ParsedWriteIntent:
    text = state.request.sms.body.strip()
    lowered = text.casefold()
    default_payer = state.request.default_payer or PaidBy.RAHIL

    if any(word in lowered for word in ("mark", "update", "change", "settle")):
        settled = (
            Settled.YES if any(word in lowered for word in ("settled", "settle", " paid")) else None
        )
        patch = ExpensePatch(settled=settled)
        vendor_match = re.search(r"(?:for|at)\s+([a-z][\w '&.-]+)", text, re.IGNORECASE)
        query = ExpenseQuery(
            month=_month_from_text(text),
            expense_contains=vendor_match.group(1).strip() if vendor_match else None,
        )
        if not patch.model_dump(exclude_none=True) or not query.model_dump(exclude_none=True):
            return ParsedWriteIntent(
                operation="clarify",
                clarification="Which expense should I update, and what should I change?",
            )
        return ParsedWriteIntent(operation="update", query=query, patch=patch)

    amount_match = re.search(r"\$?([0-9]+(?:\.[0-9]{1,2})?)", text)
    if not amount_match:
        return ParsedWriteIntent(
            operation="clarify", clarification="What was the amount of the expense?"
        )
    expense_match = re.search(
        r"(?:at|for|from)\s+(.+?)(?:\s+(?:category|paid by|notes?)\b|$)", text, re.IGNORECASE
    )
    description = expense_match.group(1).strip(" .") if expense_match else "Expense"
    explicit_payer = next(
        (payer for payer in PaidBy if payer.value.casefold() in lowered), default_payer
    )
    expense = ExpenseRow(
        date=state.request.sms.received_at.astimezone(settings.zoneinfo).date(),
        expense=description,
        cost=Decimal(amount_match.group(1)),
        paid_by=explicit_payer,
        settled=Settled.YES if "settled" in lowered else Settled.NO,
        category=_category_from_text(text),
        notes="",
    )
    return ParsedWriteIntent(operation="add", expense=expense)


def build_write_graph(
    *,
    settings: Settings | None = None,
    tools: WriteTools | None = None,
    model: BaseChatModel | None = None,
) -> Any:
    resolved_settings = settings or get_settings()
    resolved_tools = tools or WriteTools(build_sheets_gateway(resolved_settings))
    resolved_model = model if model is not None else build_chat_model(resolved_settings)

    async def interpret(state: WriteAgentState) -> dict[str, object]:
        if resolved_model is None:
            parsed = _stub_parse(state, resolved_settings)
        else:
            prompt = load_prompt_text(resolved_settings.write_agent_prompt_id, WRITE_PROMPT)
            structured = resolved_model.with_structured_output(ParsedWriteIntent)
            parsed = cast(
                ParsedWriteIntent,
                await structured.ainvoke(
                    [
                        SystemMessage(content=prompt),
                        HumanMessage(content=state.request.model_dump_json()),
                    ]
                ),
            )
        if parsed.operation == "clarify":
            return {
                "operation": parsed.operation,
                "result": AgentResult(
                    status=ResultStatus.CLARIFICATION,
                    message=parsed.clarification or "Please provide more expense details.",
                ),
            }
        return parsed.model_dump(exclude_none=True)

    async def execute(state: WriteAgentState) -> dict[str, object]:
        if state.operation == "clarify":
            return {}
        if state.operation == "add" and state.expense:
            record = await resolved_tools.append_expense(state.expense)
            return {
                "result": AgentResult(
                    status=ResultStatus.SUCCESS,
                    message=(
                        f"Added ${state.expense.cost:.2f} for {state.expense.expense} "
                        f"to {record.worksheet}."
                    ),
                    data={"record": record.model_dump(mode="json")},
                )
            }
        if state.operation == "update" and state.query and state.patch:
            candidates = await resolved_tools.find_update_candidates(state.query)
            if not candidates:
                return {
                    "candidates": [],
                    "result": AgentResult(
                        status=ResultStatus.NOT_FOUND, message="I couldn't find that expense."
                    ),
                }
            if len(candidates) > 1:
                return {
                    "candidates": candidates,
                    "result": AgentResult(
                        status=ResultStatus.CLARIFICATION,
                        message=(
                            f"I found {len(candidates)} matching expenses. Which one did you mean?"
                        ),
                    ),
                }
            updated = await resolved_tools.update_expense(candidates[0], state.patch)
            return {
                "candidates": candidates,
                "result": AgentResult(
                    status=ResultStatus.SUCCESS,
                    message=f"Updated {updated.expense.expense} in {updated.worksheet}.",
                    data={"record": updated.model_dump(mode="json")},
                ),
            }
        return {
            "result": AgentResult(
                status=ResultStatus.ERROR, message="The write request could not be completed."
            )
        }

    builder = StateGraph(WriteAgentState)
    builder.add_node("interpret", interpret)
    builder.add_node("execute", execute)
    builder.add_edge(START, "interpret")
    builder.add_edge("interpret", "execute")
    builder.add_edge("execute", END)
    return builder.compile()


graph = build_write_graph()
