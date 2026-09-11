# Expenses Agent

A Python 3.12 multi-agent scaffold for recording and querying a shared expense workbook by SMS.
LangGraph owns orchestration and each agent's workflow, while the official A2A SDK is the only
runtime boundary between the supervisor and the specialized agents.

```text
Twilio SMS -> Orchestrator :8000 -> A2A -> Write agent :8002 -> Google Sheets
                                  -> A2A -> Read agent  :8001 -> Google Sheets
```

The repository defaults to deterministic model and in-memory Sheets adapters, so it starts and can
be tested without cloud credentials. Set `MODEL_BACKEND=anthropic` and `SHEETS_BACKEND=google` to
activate the real integration seams.

## Architecture

- `orchestrator`: validates the Twilio webhook and sender, routes one or more actions, calls write
  before read for compound requests, and returns a synchronous TwiML response.
- `agents/write`: interprets add/update requests and exposes only append, candidate search, and
  single-row update tools.
- `agents/read`: interprets queries and exposes only search and aggregation tools.
- `domain`: versioned A2A request/result payloads and the exact worksheet row schema.
- `integrations`: Twilio validation, fake/Google Sheets implementations, and local idempotency.

Each service owns its own compiled graph and process. The read and write graphs are never imported
by the orchestrator. Requests and responses cross the service boundary as versioned JSON objects in
A2A protobuf `Part.data` values.

## Workbook contract

Every full-month tab (`January` through `December`) must use this header row in exactly this order:

```text
Date | Expense | Cost | Paid By | Settled | Category | Notes
```

- `Paid By`: `Rahil` or `Karishma`
- `Settled`: `Y` or `N`; new expenses default to `N`
- `Category`: `Misc`, `Transportation`, `Rent`, `Food / Drinks`, or `Groceries`
- Dates are written as `MM/DD/YYYY`; costs are written as numeric values.
- Updates only proceed when exactly one row matches. Cross-month date corrections are rejected.

## Setup

Install Python 3.12 and Poetry 2, then run:

```bash
poetry env use python3.12
poetry install
cp .env.example .env
```

Do not replace an existing `.env`; merge the example keys into it. The settings layer accepts
`TWILIO_SID` and `TWILIO_CLIENT_SECRET` as aliases for the standard `TWILIO_ACCOUNT_SID` and
`TWILIO_AUTH_TOKEN` names.

Configure these values for real integrations:

- `AUTHORIZED_SENDER_RAHIL` and `AUTHORIZED_SENDER_KARISHMA`, in E.164 format
- `ANTHROPIC_API_KEY`, plus `MODEL_BACKEND=anthropic`
- `GOOGLE_SHEETS_SPREADSHEET_ID`, plus `SHEETS_BACKEND=google`; authentication defaults to
  Application Default Credentials
- optional LangSmith prompt IDs for the supervisor, read agent, and write agent

For local development, authenticate without a downloaded service-account key:

```bash
gcloud auth application-default login \
  --client-id-file=/path/to/oauth-client.json \
  --scopes=openid,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/spreadsheets
```

Leave `GOOGLE_APPLICATION_CREDENTIALS` blank when using this flow. The Google account used for the
login must have Editor access to the workbook. An approved service-account JSON path remains
supported for deployed environments; never commit that credential file.

## Run locally

Start the full local stack, including ngrok, with one command:

```bash
./scripts/run_local.sh
```

The script waits for all three health checks, prints the complete temporary Twilio webhook URL,
and keeps the processes running until you press `Ctrl+C`. Update Twilio with the printed URL and
use `POST`. A new free ngrok URL is normally assigned each time the script starts.

Alternatively, start each service in its own terminal:

```bash
poetry run expenses-read-agent
poetry run expenses-write-agent
poetry run expenses-orchestrator
```

Endpoints:

- Orchestrator health: `GET http://127.0.0.1:8000/health`
- Twilio webhook: `POST http://127.0.0.1:8000/webhooks/twilio/sms`
- Read agent card: `GET http://127.0.0.1:8001/.well-known/agent-card.json`
- Write agent card: `GET http://127.0.0.1:8002/.well-known/agent-card.json`
- Each A2A JSON-RPC endpoint is `POST /` on its agent port.

Twilio must be configured with an internet-reachable HTTPS URL, normally through a development
tunnel or deployed ingress. Signature validation is enabled by default. Keep the externally visible
URL unchanged through any proxy because it is part of Twilio's signature calculation.

The fake Sheets backend is process-local: it is intended for unit tests and service exploration,
not shared state across three independently running processes. Use the Google backend for a real
three-service flow.

## LangSmith and prompts

`langgraph.json` registers `supervisor`, `read_agent`, and `write_agent`, allowing each graph to be
opened independently in LangSmith Studio. Local fallback prompts keep the scaffold runnable. When a
prompt ID is configured, the corresponding prompt is pulled from LangSmith and must instruct the
model to produce the Pydantic structured output declared by that graph.

## Quality checks

```bash
poetry run pytest
poetry run ruff check src tests
poetry run ruff format --check src tests
poetry run mypy src
```

Tests do not call Twilio, Anthropic, LangSmith, or Google. The contract suite does exercise a real
in-process A2A client/server JSON-RPC exchange.

## Production follow-ups

The initial scaffold intentionally uses synchronous Twilio processing and in-memory A2A task and
idempotency stores. Before production, add durable idempotency/checkpoint storage, async SMS result
delivery, authentication between internal services, concurrency controls around row updates, and
deployment-specific secret management.
