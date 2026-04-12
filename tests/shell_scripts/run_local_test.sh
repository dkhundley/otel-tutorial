#!/bin/bash

# Exit immediately if any command fails.
# This keeps the script deterministic and prevents partial-success runs.
set -e

# Navigate to the root of the Git repository
cd "$(git rev-parse --show-toplevel)"
ROOT_DIR="$(pwd)"

# Color output for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PORT=8000
APP_DIR="src"
API_MODULE="pizza_api:pizza_api"
API_PID=""

# Telemetry defaults for local-file exports.
# - OTEL_EXPORT_TARGET=file tells otel_config.py to write telemetry to files.
# - OTEL_LOCAL_EXPORT_DIR is where traces, metrics, and logs are written.
# - Keep SDK enabled by default so telemetry is produced in this test.
OTEL_EXPORT_TARGET_INPUT="${OTEL_EXPORT_TARGET:-file}"
OTEL_LOCAL_EXPORT_DIR_INPUT="${OTEL_LOCAL_EXPORT_DIR:-$ROOT_DIR/telemetry_output/local_test}"
OTEL_DISABLED="${OTEL_SDK_DISABLED:-false}"

# Use the workspace virtual environment if available, otherwise fall back to python3.
if [ -x ".venv/bin/python" ]; then
	PYTHON_CMD="$ROOT_DIR/.venv/bin/python"
else
	PYTHON_CMD="python3"
fi

cleanup() {
	# Always stop the API process we started, even if the script errors out.
	# Guard with kill -0 so we do not attempt to kill a non-existent PID.
	if [ -n "$API_PID" ] && kill -0 "$API_PID" 2>/dev/null; then
		echo -e "${YELLOW}Stopping local API process...${NC}"
		kill "$API_PID" 2>/dev/null || true
		wait "$API_PID" 2>/dev/null || true
	fi
}

# Ensure cleanup runs for success, error, and interruption paths.
trap cleanup EXIT

# Free the HTTP port in case a prior local run left a process behind.
# This keeps repeat runs predictable.
echo -e "${YELLOW}Checking for existing process on port ${PORT}...${NC}"
EXISTING_PIDS=$(lsof -ti tcp:"$PORT" || true)
if [ -n "$EXISTING_PIDS" ]; then
	echo -e "${YELLOW}Stopping existing process(es) on port ${PORT}...${NC}"
	echo "$EXISTING_PIDS" | xargs kill 2>/dev/null || true
fi

# Wait until the port is fully released so requests do not hit a stale process.
for _ in {1..20}; do
	if ! lsof -ti tcp:"$PORT" >/dev/null 2>&1; then
		break
	fi
	sleep 1
done

if lsof -ti tcp:"$PORT" >/dev/null 2>&1; then
	echo -e "${RED}Error: Port ${PORT} is still in use after cleanup${NC}"
	exit 1
fi

# Reset telemetry output directory for a clean test run.
echo -e "${YELLOW}Preparing local telemetry directory...${NC}"
rm -rf "$OTEL_LOCAL_EXPORT_DIR_INPUT"
mkdir -p "$OTEL_LOCAL_EXPORT_DIR_INPUT"

echo -e "${YELLOW}Starting local API...${NC}"
echo -e "${YELLOW}OTEL export target: ${OTEL_EXPORT_TARGET_INPUT}${NC}"
echo -e "${YELLOW}OTEL local export dir: ${OTEL_LOCAL_EXPORT_DIR_INPUT}${NC}"
echo -e "${YELLOW}OTEL_SDK_DISABLED: ${OTEL_DISABLED}${NC}"

# Start FastAPI in the background from src so relative files (e.g. pizza_menu.json)
# resolve the same way they do in the container image.
(
	cd "$APP_DIR"
	OTEL_EXPORT_TARGET="$OTEL_EXPORT_TARGET_INPUT" \
	OTEL_LOCAL_EXPORT_DIR="$OTEL_LOCAL_EXPORT_DIR_INPUT" \
	OTEL_SDK_DISABLED="$OTEL_DISABLED" \
	"$PYTHON_CMD" -m uvicorn "$API_MODULE" --host 0.0.0.0 --port "$PORT"
) &
API_PID=$!

# Readiness loop:
# Poll /menu for up to 20 seconds to allow app startup and instrumentation init.
echo -e "${YELLOW}Waiting for local API to start...${NC}"
READY=0
for _ in {1..20}; do
	if curl -s "http://localhost:$PORT/menu" >/dev/null; then
		READY=1
		break
	fi
	sleep 1
done

if [ "$READY" -ne 1 ]; then
	echo -e "${RED}Error: Local API failed to start${NC}"
	exit 1
fi

echo -e "${GREEN}Local API is running!${NC}"

# Functional test:
# Submit all sample pizza orders to confirm endpoint behavior and ensure
# telemetry-producing code paths execute across a variety of order types.
SAMPLE_ORDERS_FILE="$ROOT_DIR/tests/sample_data/sample_pizza_orders.json"
ORDER_COUNT=$("$PYTHON_CMD" -c "import json; orders=json.load(open('$SAMPLE_ORDERS_FILE')); print(len(orders))")
echo -e "${YELLOW}Testing API with curl - Submitting ${ORDER_COUNT} pizza orders...${NC}"
for i in $(seq 0 $((ORDER_COUNT - 1))); do
	ORDER=$("$PYTHON_CMD" -c "import json; orders=json.load(open('$SAMPLE_ORDERS_FILE')); print(json.dumps(orders[$i]))")
	echo -e "${YELLOW}Submitting order $((i + 1)) of ${ORDER_COUNT}...${NC}"
	RESPONSE=$(curl -s -X POST "http://localhost:$PORT/order" \
	  -H "Content-Type: application/json" \
	  -d "$ORDER")
	echo -e "${GREEN}Response:${NC}"
	echo "$RESPONSE" | "$PYTHON_CMD" -m json.tool
done

# Hit stats and health so we produce additional spans/logs/metrics.
curl -s "http://localhost:$PORT/stats" >/dev/null
curl -s "http://localhost:$PORT/health" >/dev/null

# Allow one short interval so the periodic metric reader flushes to file.
sleep 3

echo -e "${GREEN}Telemetry files:${NC}"
ls -lah "$OTEL_LOCAL_EXPORT_DIR_INPUT"

# Assert that all telemetry signals were written.
TRACE_FILE="$OTEL_LOCAL_EXPORT_DIR_INPUT/traces.jsonl"
METRICS_FILE="$OTEL_LOCAL_EXPORT_DIR_INPUT/metrics.jsonl"
LOGS_FILE="$OTEL_LOCAL_EXPORT_DIR_INPUT/logs.jsonl"

if [ ! -s "$TRACE_FILE" ] || [ ! -s "$METRICS_FILE" ] || [ ! -s "$LOGS_FILE" ]; then
	echo -e "${RED}Error: Expected telemetry files were not generated correctly${NC}"
	echo -e "${RED}Expected non-empty files:${NC}"
	echo -e "${RED}- $TRACE_FILE${NC}"
	echo -e "${RED}- $METRICS_FILE${NC}"
	echo -e "${RED}- $LOGS_FILE${NC}"
	exit 1
fi

echo -e "${GREEN}Test complete!${NC}"
