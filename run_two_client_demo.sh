#!/usr/bin/env bash
set -euo pipefail

# Runs a full demo with:
# 1) server started in background
# 2) simulator with exactly two clients in foreground (runs until Ctrl+C)
# 3) automatic cleanup and sample DB output

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$ROOT_DIR/server"
SIM_DIR="$ROOT_DIR/client/simulator"

HOST="127.0.0.1"
PORT="${PORT:-9000}"
DASHBOARD_PORT="${DASHBOARD_PORT:-8080}"
DB_PATH="$SERVER_DIR/data/readings.db"
LOG_DIR="$ROOT_DIR/logs"

SERVER_LOG="$LOG_DIR/server_demo.log"
SIM_LOG="$LOG_DIR/simulator_demo.log"
DASHBOARD_LOG="$LOG_DIR/dashboard_demo.log"

SERVER_PID=""
DASHBOARD_PID=""

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "sport = :$port" | grep -q LISTEN
    return
  fi

  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN -Pn >/dev/null 2>&1
    return
  fi

  return 1
}

pick_available_port() {
  local start_port="$1"
  local candidate="$start_port"

  while port_in_use "$candidate"; do
    candidate=$((candidate + 1))
  done

  echo "$candidate"
}

cleanup() {
  if [[ -n "$DASHBOARD_PID" ]] && kill -0 "$DASHBOARD_PID" 2>/dev/null; then
    kill "$DASHBOARD_PID" 2>/dev/null || true
    wait "$DASHBOARD_PID" 2>/dev/null || true
  fi

  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}

on_interrupt() {
  echo
  echo "[demo] Ctrl+C received, shutting down..."
  exit 0
}

trap cleanup EXIT
trap on_interrupt INT TERM

mkdir -p "$SERVER_DIR/data"
mkdir -p "$LOG_DIR"

PORT="$(pick_available_port "$PORT")"
DASHBOARD_PORT="$(pick_available_port "$DASHBOARD_PORT")"

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

echo "[demo] Starting dashboard on $HOST:$DASHBOARD_PORT"
(
  cd "$SERVER_DIR"
  python3 src/dashboard.py --host "$HOST" --port "$DASHBOARD_PORT" --db "$DB_PATH" >"$DASHBOARD_LOG" 2>&1
) &
DASHBOARD_PID="$!"

sleep 1
if ! kill -0 "$DASHBOARD_PID" 2>/dev/null; then
  echo "[demo] Dashboard failed to start. Check $DASHBOARD_LOG"
  exit 1
fi

echo "[demo] Web dashboard: http://$HOST:$DASHBOARD_PORT"

echo "[demo] Running simulator with 2 clients (press Ctrl+C to stop)"
(
  cd "$SIM_DIR"
  python3 multi_client_simulator.py \
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
