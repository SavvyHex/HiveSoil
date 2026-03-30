#!/usr/bin/env python3
"""Minimal live dashboard for soil moisture readings."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


HTML_PAGE = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>HiveSoil Live Dashboard</title>
  <style>
    :root {
      --bg: #f5f2ea;
      --card: #fffdf8;
      --ink: #29241d;
      --muted: #7f7567;
      --accent: #1d7a58;
      --accent-soft: #d6efe5;
      --warn: #bf5b2c;
      --border: #e6ddcf;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(1200px 600px at -10% -10%, #f0e8d8 10%, transparent 70%),
        radial-gradient(700px 400px at 110% 0%, #d5e8de 5%, transparent 70%),
        var(--bg);
      min-height: 100vh;
    }

    .wrap {
      max-width: 1100px;
      margin: 0 auto;
      padding: 20px;
    }

    .head {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 16px;
      margin-bottom: 18px;
    }

    h1 {
      margin: 0;
      font-size: clamp(1.35rem, 2.6vw, 2.1rem);
      letter-spacing: 0.01em;
    }

    .sub {
      color: var(--muted);
      font-size: 0.95rem;
      margin-top: 3px;
    }

    .pill {
      background: var(--accent-soft);
      color: var(--accent);
      border: 1px solid #bde4d3;
      border-radius: 999px;
      padding: 7px 11px;
      font-size: 0.82rem;
      white-space: nowrap;
    }

    .grid {
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      margin-bottom: 14px;
    }

    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px;
      box-shadow: 0 6px 22px rgba(29, 39, 36, 0.06);
    }

    .label {
      color: var(--muted);
      font-size: 0.86rem;
      margin-bottom: 8px;
    }

    .value {
      font-size: clamp(1.3rem, 3vw, 1.8rem);
      font-weight: 640;
      color: var(--ink);
    }

    .table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.92rem;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 6px 22px rgba(29, 39, 36, 0.06);
    }

    .table th,
    .table td {
      text-align: left;
      padding: 10px;
      border-bottom: 1px solid #efe7da;
    }

    .table th {
      font-size: 0.8rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
      background: #faf6ef;
    }

    .table tr:last-child td { border-bottom: 0; }

    .status {
      margin-top: 10px;
      color: var(--muted);
      font-size: 0.85rem;
    }

    .dry { color: var(--warn); font-weight: 600; }

    @media (max-width: 840px) {
      .grid { grid-template-columns: 1fr 1fr; }
    }

    @media (max-width: 560px) {
      .head { align-items: flex-start; flex-direction: column; }
      .grid { grid-template-columns: 1fr; }
      .table { font-size: 0.84rem; }
      .table th, .table td { padding: 8px; }
    }
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"head\">
      <div>
        <h1>HiveSoil Live Dashboard</h1>
        <div class=\"sub\">Realtime view of incoming soil moisture readings</div>
      </div>
      <div class=\"pill\" id=\"updated\">Loading...</div>
    </div>

    <div class=\"grid\">
      <div class=\"card\">
        <div class=\"label\">Connected Devices (seen in latest records)</div>
        <div class=\"value\" id=\"deviceCount\">-</div>
      </div>
      <div class=\"card\">
        <div class=\"label\">Average Moisture</div>
        <div class=\"value\" id=\"avgMoisture\">-</div>
      </div>
      <div class=\"card\">
        <div class=\"label\">Total Readings Saved</div>
        <div class=\"value\" id=\"totalReadings\">-</div>
      </div>
    </div>

    <table class=\"table\" id=\"recentTable\">
      <thead>
        <tr>
          <th>ID</th>
          <th>Device</th>
          <th>Moisture %</th>
          <th>Raw</th>
          <th>Received</th>
          <th>Client IP</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>

    <div class=\"status\" id=\"status\">Waiting for data...</div>
  </div>

  <script>
    const REFRESH_MS = 2000;

    function esc(v) {
      return String(v)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    }

    function fmtPercent(v) {
      const n = Number(v);
      if (Number.isNaN(n)) return '-';
      return `${n.toFixed(2)}%`;
    }

    function render(data) {
      document.getElementById('deviceCount').textContent = data.device_count;
      document.getElementById('avgMoisture').textContent = fmtPercent(data.avg_moisture_percent);
      document.getElementById('totalReadings').textContent = data.total_readings;
      document.getElementById('updated').textContent = `Updated ${new Date(data.server_time).toLocaleTimeString()}`;
      document.getElementById('status').textContent = `Auto-refresh every ${REFRESH_MS / 1000}s`;

      const tbody = document.querySelector('#recentTable tbody');
      tbody.innerHTML = '';

      for (const row of data.recent_readings) {
        const tr = document.createElement('tr');
        const pct = Number(row.moisture_percent);
        const pctClass = pct < 30 ? 'dry' : '';
        tr.innerHTML = `
          <td>${esc(row.id)}</td>
          <td>${esc(row.device_id)}</td>
          <td class="${pctClass}">${esc(fmtPercent(row.moisture_percent))}</td>
          <td>${esc(row.moisture_raw)}</td>
          <td>${esc(row.server_received_at)}</td>
          <td>${esc(row.client_ip)}</td>
        `;
        tbody.appendChild(tr);
      }
    }

    async function load() {
      try {
        const res = await fetch('/api/summary', { cache: 'no-store' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        render(data);
      } catch (err) {
        document.getElementById('status').textContent = `Fetch failed: ${err.message}`;
      }
    }

    load();
    setInterval(load, REFRESH_MS);
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    db_path: Path

    def _set_headers(self, status: int, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path == "/" or path == "/index.html":
            self._set_headers(HTTPStatus.OK, "text/html; charset=utf-8")
            self.wfile.write(HTML_PAGE.encode("utf-8"))
            return

        if path == "/api/summary":
            payload = self._query_summary()
            self._set_headers(HTTPStatus.OK, "application/json; charset=utf-8")
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        self._set_headers(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8")
        self.wfile.write(b'{"error":"Not found"}')

    def log_message(self, fmt: str, *args: object) -> None:
        # Keep logs compact while polling.
        return

    def _query_summary(self) -> dict[str, object]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        total_readings = conn.execute("SELECT COUNT(*) AS c FROM readings").fetchone()["c"]
        avg_row = conn.execute("SELECT AVG(moisture_percent) AS avg_pct FROM readings").fetchone()
        avg_moisture = float(avg_row["avg_pct"]) if avg_row["avg_pct"] is not None else 0.0

        recent_rows = conn.execute(
            """
            SELECT id, device_id, moisture_raw, moisture_percent, server_received_at, client_ip
            FROM readings
            ORDER BY id DESC
            LIMIT 25
            """
        ).fetchall()

        conn.close()

        device_count = len({row["device_id"] for row in recent_rows})

        return {
            "server_time": datetime.now(timezone.utc).isoformat(),
            "total_readings": total_readings,
            "device_count": device_count,
            "avg_moisture_percent": round(avg_moisture, 2),
            "recent_readings": [dict(row) for row in recent_rows],
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live web dashboard for soil moisture data")
    parser.add_argument("--host", default="127.0.0.1", help="Dashboard bind host")
    parser.add_argument("--port", type=int, default=8080, help="Dashboard bind port")
    parser.add_argument("--db", default="data/readings.db", help="Path to SQLite database")
    return parser.parse_args()


def ensure_schema(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            moisture_raw INTEGER NOT NULL,
            moisture_percent REAL NOT NULL,
            sensor_pin INTEGER,
            firmware_version TEXT,
            client_timestamp TEXT,
            server_received_at TEXT NOT NULL,
            client_ip TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def main() -> None:
    args = parse_args()
    db_path = Path(args.db)
    ensure_schema(db_path)

    DashboardHandler.db_path = db_path

    httpd = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"[dashboard] Serving on http://{args.host}:{args.port}")
    print(f"[dashboard] Using DB: {db_path}")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[dashboard] Shutdown requested")


if __name__ == "__main__":
    main()
