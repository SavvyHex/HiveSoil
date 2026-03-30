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
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
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

    .table-controls {
      margin-top: 10px;
      display: flex;
      justify-content: center;
    }

    .btn {
      border: 1px solid var(--border);
      background: #fff8ec;
      color: #5f5548;
      border-radius: 999px;
      padding: 7px 14px;
      font-size: 0.84rem;
      cursor: pointer;
    }

    .btn:disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }

    .charts-grid {
      margin-top: 14px;
      display: grid;
      gap: 14px;
      grid-template-columns: 1fr 1fr;
    }

    .chart-title {
      font-size: 0.95rem;
      color: #5f5448;
      margin-bottom: 6px;
      font-weight: 600;
    }

    .chart-wrap {
      margin-top: 8px;
      width: 100%;
      overflow-x: auto;
    }

    .mini-chart {
      width: 100%;
      min-height: 280px;
      border: 1px solid #efe7da;
      border-radius: 10px;
      background: linear-gradient(180deg, #fffdf8 0%, #fbf6ec 100%);
      display: block;
    }

    .status {
      margin-top: 10px;
      color: var(--muted);
      font-size: 0.85rem;
    }

    .dry { color: var(--warn); font-weight: 600; }

    @media (max-width: 840px) {
      .grid { grid-template-columns: 1fr 1fr; }
      .charts-grid { grid-template-columns: 1fr; }
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
  <div class="wrap">
    <div class="head">
      <div>
        <h1>HiveSoil Live Dashboard</h1>
        <div class="sub">Realtime view of incoming soil moisture readings</div>
      </div>
      <div class="pill" id="updated">Loading...</div>
    </div>

    <div class="grid">
      <div class="card">
        <div class="label">Connected Devices (seen in latest records)</div>
        <div class="value" id="deviceCount">-</div>
      </div>
      <div class="card">
        <div class="label">Average Moisture</div>
        <div class="value" id="avgMoisture">-</div>
      </div>
      <div class="card">
        <div class="label">Total Readings Saved</div>
        <div class="value" id="totalReadings">-</div>
      </div>
    </div>

    <table class="table" id="recentTable">
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

    <div class="table-controls">
      <button id="showMoreBtn" class="btn" type="button">Show more</button>
    </div>

    <div class="charts-grid">
      <div class="card">
        <div class="chart-title" id="chartATitle">Client chart A</div>
        <div class="chart-wrap">
          <svg id="chartA" class="mini-chart" viewBox="0 0 960 320" preserveAspectRatio="none"></svg>
        </div>
      </div>
      <div class="card">
        <div class="chart-title" id="chartBTitle">Client chart B</div>
        <div class="chart-wrap">
          <svg id="chartB" class="mini-chart" viewBox="0 0 960 320" preserveAspectRatio="none"></svg>
        </div>
      </div>
    </div>

    <div class="status" id="status">Waiting for data...</div>
  </div>

  <script>
    const REFRESH_MS = 2000;
    const INITIAL_VISIBLE_ROWS = 5;
    const STEP_VISIBLE_ROWS = 5;
    const CHART_COLORS = ['#20639b', '#d1495b'];
    let visibleRows = INITIAL_VISIBLE_ROWS;
    let latestRows = [];

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

    function toPointsPath(points) {
      if (points.length === 0) return '';
      let path = `M ${points[0].x} ${points[0].y}`;
      for (let i = 1; i < points.length; i += 1) {
        path += ` L ${points[i].x} ${points[i].y}`;
      }
      return path;
    }

    function renderNoDataChart(svgId, titleId, titleText, message) {
      const chart = document.getElementById(svgId);
      document.getElementById(titleId).textContent = titleText;
      chart.innerHTML = `
        <text x="50%" y="50%" text-anchor="middle" fill="#8e8477" font-size="15">
          ${esc(message)}
        </text>
      `;
    }

    function renderDeviceChart(svgId, titleId, deviceId, rows, color) {
      const chart = document.getElementById(svgId);
      const width = 960;
      const height = 320;
      const pad = { top: 18, right: 24, bottom: 42, left: 46 };
      const plotW = width - pad.left - pad.right;
      const plotH = height - pad.top - pad.bottom;

      chart.innerHTML = '';
      document.getElementById(titleId).textContent = `Client: ${deviceId}`;

      const parsed = rows
        .map((row) => ({
          ...row,
          t: new Date(row.server_received_at).getTime(),
          p: Number(row.moisture_percent),
        }))
        .filter((row) => Number.isFinite(row.t) && Number.isFinite(row.p))
        .sort((a, b) => a.t - b.t);

      if (parsed.length === 0) {
        renderNoDataChart(svgId, titleId, `Client: ${deviceId}`, 'No plottable points yet');
        return;
      }

      const minT = parsed[0].t;
      const maxT = parsed[parsed.length - 1].t;
      const rangeT = Math.max(1, maxT - minT);

      chart.insertAdjacentHTML('beforeend', `
        <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}" stroke="#cbbca8" stroke-width="1" />
        <line x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}" stroke="#cbbca8" stroke-width="1" />
        <text x="${pad.left}" y="${pad.top - 6}" fill="#8e8477" font-size="11">100%</text>
        <text x="${pad.left}" y="${height - pad.bottom + 14}" fill="#8e8477" font-size="11">0%</text>
        <text x="${pad.left}" y="${height - 8}" fill="#8e8477" font-size="11">time</text>
      `);

      const points = parsed.map((row) => {
        const x = pad.left + ((row.t - minT) / rangeT) * plotW;
        const y = pad.top + (1 - (Math.max(0, Math.min(100, row.p)) / 100)) * plotH;
        return { x: Number(x.toFixed(2)), y: Number(y.toFixed(2)) };
      });

      const pathData = toPointsPath(points);
      chart.insertAdjacentHTML('beforeend', `
        <path d="${pathData}" fill="none" stroke="${color}" stroke-width="2.7" stroke-linecap="round" stroke-linejoin="round" />
      `);

      points.forEach((point) => {
        chart.insertAdjacentHTML('beforeend', `
          <circle cx="${point.x}" cy="${point.y}" r="2.2" fill="${color}" />
        `);
      });
    }

    function renderTwoClientCharts(rows) {
      const deviceRows = {};
      for (const row of rows) {
        if (!deviceRows[row.device_id]) deviceRows[row.device_id] = [];
        deviceRows[row.device_id].push(row);
      }

      const deviceIds = Object.keys(deviceRows).sort();

      if (deviceIds.length === 0) {
        renderNoDataChart('chartA', 'chartATitle', 'Client chart A', 'No data yet');
        renderNoDataChart('chartB', 'chartBTitle', 'Client chart B', 'No data yet');
        return;
      }

      renderDeviceChart('chartA', 'chartATitle', deviceIds[0], deviceRows[deviceIds[0]], CHART_COLORS[0]);

      if (deviceIds.length > 1) {
        renderDeviceChart('chartB', 'chartBTitle', deviceIds[1], deviceRows[deviceIds[1]], CHART_COLORS[1]);
      } else {
        renderNoDataChart('chartB', 'chartBTitle', 'Client chart B', 'Waiting for second client');
      }
    }

    function renderTable(rows) {
      const tbody = document.querySelector('#recentTable tbody');
      tbody.innerHTML = '';

      const visible = rows.slice(0, visibleRows);
      for (const row of visible) {
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

      const btn = document.getElementById('showMoreBtn');
      if (visibleRows >= rows.length) {
        btn.textContent = 'All readings shown';
        btn.disabled = true;
      } else {
        btn.textContent = 'Show more';
        btn.disabled = false;
      }
    }

    function render(data) {
      latestRows = data.recent_readings || [];

      if (latestRows.length < visibleRows) {
        visibleRows = Math.max(INITIAL_VISIBLE_ROWS, latestRows.length);
      }

      document.getElementById('deviceCount').textContent = data.device_count;
      document.getElementById('avgMoisture').textContent = fmtPercent(data.avg_moisture_percent);
      document.getElementById('totalReadings').textContent = data.total_readings;
      document.getElementById('updated').textContent = `Updated ${new Date(data.server_time).toLocaleTimeString()}`;
      document.getElementById('status').textContent = `Auto-refresh every ${REFRESH_MS / 1000}s`;

      renderTable(latestRows);
      renderTwoClientCharts(latestRows);
    }

    function onShowMore() {
      visibleRows += STEP_VISIBLE_ROWS;
      renderTable(latestRows);
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
    document.getElementById('showMoreBtn').addEventListener('click', onShowMore);
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
          LIMIT 120
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
