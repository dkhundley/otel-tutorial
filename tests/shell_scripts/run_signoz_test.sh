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

# Telemetry defaults:
# - If OTEL_EXPORTER_OTLP_ENDPOINT is not provided, use the SigNoz host/port.
# - Keep SDK enabled by default so traces/metrics/logs are exported in this test.
OTEL_ENDPOINT_INPUT="${OTEL_EXPORTER_OTLP_ENDPOINT:-davids-mac-mini.local:4317}"
OTEL_DISABLED="${OTEL_SDK_DISABLED:-false}"

# Use the workspace virtual environment if available, otherwise fall back to python3.
if [ -x ".venv/bin/python" ]; then
	PYTHON_CMD="$ROOT_DIR/.venv/bin/python"
else
	PYTHON_CMD="python3"
fi

# Normalize the OTLP endpoint to host:port form.
# We accept values with or without scheme, e.g.:
# - http://collector.local:4317
# - https://collector.local:4317
# - collector.local:4317
if [[ "$OTEL_ENDPOINT_INPUT" == http://* ]]; then
	OTEL_ENDPOINT_STRIPPED="${OTEL_ENDPOINT_INPUT#http://}"
elif [[ "$OTEL_ENDPOINT_INPUT" == https://* ]]; then
	OTEL_ENDPOINT_STRIPPED="${OTEL_ENDPOINT_INPUT#https://}"
else
	OTEL_ENDPOINT_STRIPPED="$OTEL_ENDPOINT_INPUT"
fi

OTEL_HOST="${OTEL_ENDPOINT_STRIPPED%%:*}"
OTEL_PORT="${OTEL_ENDPOINT_STRIPPED##*:}"

# If no explicit port was provided, default to OTLP gRPC port 4317.
if [ "$OTEL_HOST" = "$OTEL_PORT" ]; then
	OTEL_PORT="4317"
fi

# Resolve host to IPv4 when possible.
# This avoids occasional .local + IPv6/mDNS instability seen with gRPC exporters.
# If resolution fails, we fall back to the original host to preserve behavior.
OTEL_RESOLVED_HOST="$($PYTHON_CMD -c "import socket,sys;h=sys.argv[1];
try:
    print(socket.getaddrinfo(h, None, socket.AF_INET, socket.SOCK_STREAM)[0][4][0])
except Exception:
    print(h)
" "$OTEL_HOST")"
OTEL_ENDPOINT="${OTEL_RESOLVED_HOST}:${OTEL_PORT}"

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

echo -e "${YELLOW}Starting local API...${NC}"
echo -e "${YELLOW}OTEL endpoint input: ${OTEL_ENDPOINT_INPUT}${NC}"
echo -e "${YELLOW}OTEL endpoint resolved: ${OTEL_ENDPOINT}${NC}"
echo -e "${YELLOW}OTEL_SDK_DISABLED: ${OTEL_DISABLED}${NC}"

# Preflight check: warn if collector is currently unreachable.
# This is informational only; the script still runs to test API behavior.
if ! nc -z "$OTEL_RESOLVED_HOST" "$OTEL_PORT" >/dev/null 2>&1; then
	echo -e "${YELLOW}Warning: OTLP endpoint ${OTEL_ENDPOINT} is not reachable right now.${NC}"
fi

# Start FastAPI in the background from src so relative files (e.g. pizza_menu.json)
# resolve the same way they do in the container image.
(
	cd "$APP_DIR"
	# Force explicit gRPC OTLP settings for consistency with SigNoz defaults.
	# Using explicit signal protocol variables avoids implicit SDK defaults differing
	# between SDK versions or environments.
	OTEL_EXPORTER_OTLP_ENDPOINT="$OTEL_ENDPOINT" \
	OTEL_EXPORTER_OTLP_PROTOCOL="grpc" \
	OTEL_EXPORTER_OTLP_INSECURE="true" \
	OTEL_EXPORTER_OTLP_METRICS_PROTOCOL="grpc" \
	OTEL_EXPORTER_OTLP_TRACES_PROTOCOL="grpc" \
	OTEL_EXPORTER_OTLP_LOGS_PROTOCOL="grpc" \
	OTEL_SDK_DISABLED="$OTEL_DISABLED" \
	exec "$PYTHON_CMD" -m uvicorn "$API_MODULE" --host 0.0.0.0 --port "$PORT"
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

# Pretty-print JSON for human readability in terminal output.
echo -e "${GREEN}All orders submitted!${NC}"

echo -e "${GREEN}Test complete!${NC}"
