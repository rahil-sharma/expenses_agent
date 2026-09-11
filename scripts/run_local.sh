#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PIDS=()
LAST_PID=""
STOP_REQUESTED=false

if [[ ${1:-} == "-h" || ${1:-} == "--help" ]]; then
  echo "Usage: ./scripts/run_local.sh"
  echo "Starts the orchestrator, read agent, write agent, and ngrok tunnel."
  exit 0
elif (($# > 0)); then
  echo "Unknown argument: $1" >&2
  echo "Usage: ./scripts/run_local.sh" >&2
  exit 2
fi

TEMP_ROOT=${TMPDIR:-/tmp}
RUN_DIR="$(mktemp -d "${TEMP_ROOT%/}/expenses-agent.XXXXXX")"

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM

  if ((${#PIDS[@]})); then
    kill "${PIDS[@]}" 2>/dev/null || true
    wait "${PIDS[@]}" 2>/dev/null || true
  fi

  if [[ "$STOP_REQUESTED" == true ]]; then
    echo
    echo "Expense Agent services and ngrok stopped."
  elif ((exit_code != 0)); then
    echo >&2
    echo "Startup failed. Logs are available in: $RUN_DIR" >&2
  fi
}

request_stop() {
  STOP_REQUESTED=true
  exit 0
}

trap cleanup EXIT
trap request_stop INT TERM

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command not found: $1" >&2
    exit 1
  fi
}

start_process() {
  local name=$1
  shift
  "$@" >"$RUN_DIR/$name.log" 2>&1 &
  LAST_PID=$!
  PIDS+=("$LAST_PID")
}

wait_for_health() {
  local name=$1
  local port=$2
  local pid=$3

  for _ in {1..80}; do
    if curl --silent --fail "http://127.0.0.1:$port/health" >/dev/null; then
      return 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "$name exited during startup:" >&2
      tail -n 30 "$RUN_DIR/$name.log" >&2
      return 1
    fi
    sleep 0.25
  done

  echo "$name did not become healthy on port $port:" >&2
  tail -n 30 "$RUN_DIR/$name.log" >&2
  return 1
}

wait_for_ngrok_url() {
  local pid=$1

  for _ in {1..80}; do
    if public_url=$(poetry run python -c '
import json
from urllib.request import urlopen

with urlopen("http://127.0.0.1:4040/api/tunnels", timeout=1) as response:
    tunnels = json.load(response)["tunnels"]
print(next(tunnel["public_url"] for tunnel in tunnels if tunnel["proto"] == "https"))
' 2>/dev/null); then
      printf '%s\n' "$public_url"
      return 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "ngrok exited during startup:" >&2
      tail -n 30 "$RUN_DIR/ngrok.log" >&2
      return 1
    fi
    sleep 0.25
  done

  echo "ngrok did not publish an HTTPS URL:" >&2
  tail -n 30 "$RUN_DIR/ngrok.log" >&2
  return 1
}

cd "$PROJECT_DIR"

require_command poetry
require_command ngrok
require_command curl
require_command lsof

if [[ ! -f .env ]]; then
  echo "Missing $PROJECT_DIR/.env. Copy .env.example and configure it first." >&2
  exit 1
fi

if ! ngrok config check >/dev/null 2>&1; then
  echo "ngrok is not authenticated. Run: ngrok config add-authtoken YOUR_TOKEN" >&2
  exit 1
fi

for port in 8000 8001 8002 4040; do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is already in use. Stop the existing process and retry." >&2
    exit 1
  fi
done

echo "Starting Expense Agent services..."
echo "Runtime logs: $RUN_DIR"

start_process orchestrator poetry run expenses-orchestrator
orchestrator_pid=$LAST_PID
start_process read-agent poetry run expenses-read-agent
read_pid=$LAST_PID
start_process write-agent poetry run expenses-write-agent
write_pid=$LAST_PID

wait_for_health "orchestrator" 8000 "$orchestrator_pid"
wait_for_health "read-agent" 8001 "$read_pid"
wait_for_health "write-agent" 8002 "$write_pid"

start_process ngrok ngrok http 8000 --log=stdout --log-format=json
ngrok_pid=$LAST_PID
public_url=$(wait_for_ngrok_url "$ngrok_pid")
webhook_url="${public_url%/}/webhooks/twilio/sms"

echo
echo "All services are healthy."
echo "Twilio webhook URL:"
echo "$webhook_url"
echo "Twilio request method: POST"
echo
echo "Keep this terminal open. Press Ctrl+C to stop everything."

while true; do
  for pid in "${PIDS[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "A managed process stopped unexpectedly. Check logs in $RUN_DIR" >&2
      exit 1
    fi
  done
  sleep 2
done
