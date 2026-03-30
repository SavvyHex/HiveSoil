#!/usr/bin/env bash
set -euo pipefail

# Runs a full demo with:
# 1) server started in background
# 2) simulator with exactly two clients in foreground for N seconds
# 3) automatic cleanup and sample DB output

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$ROOT_DIR/server"
SIM_DIR="$ROOT_DIR/client/simulator"

HOST="127.0.0.1"
PORT="9000"
DB_PATH="$SERVER_DIR/data/readings.db"
DURATION_SECONDS="${1:-20}"

SERVER_LOG="$SERVER_DIR/server_demo.log"
SIM_LOG="$SIM_DIR/simulator_demo.log"

SERVER_PID=""

cleanup() {
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

mkdir -p "$SERVER_DIR/data"

echo "[demo] Starting server on $HOST:$PORT"
(
  cd "$SERVER_DIR"
  python3 src/server.py --host "$HOST" --port "$PORT" --db "$DB_PATH" >"$SERVER_LOG" 2>&1
) &
SERVER_PID="$!"

sleep 1
if ! kill -0 "$SERVER_PID" 2>/dev/null; then
  echo "[demo] Server failed to start. Check $SERVER_LOG"
  exit 1
fi

echo "[demo] Running simulator with 2 clients for ${DURATION_SECONDS}s"
(
  cd "$SIM_DIR"
  timeout "$DURATION_SECONDS" python3 multi_client_simulator.py \
    --host "$HOST" \
    --port "$PORT" \
    --clients 2 \
    --interval 3
) | tee "$SIM_LOG" || true

echo "[demo] Stopping server"
cleanup
SERVER_PID=""

echo "[demo] Latest stored readings"
(
  cd "$SERVER_DIR"
  python3 src/inspect_readings.py --db "$DB_PATH" --limit 10
)

echo "[demo] Done"
