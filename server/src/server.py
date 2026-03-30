#!/usr/bin/env python3
"""Async multi-client TCP server for soil moisture ingestion."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class Reading:
    device_id: str
    moisture_raw: int
    moisture_percent: float
    sensor_pin: int | None
    firmware_version: str | None
    client_timestamp: str | None
    server_received_at: str
    client_ip: str


class SoilMoistureServer:
    def __init__(self, host: str, port: int, db_path: Path) -> None:
        self.host = host
        self.port = port
        self.db_path = db_path
        self._db = sqlite3.connect(db_path)
        self._db.execute("PRAGMA journal_mode=WAL;")
        self._db.execute(
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
        self._db.commit()

    async def start(self) -> None:
        server = await asyncio.start_server(self._handle_client, self.host, self.port)
        addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
        print(f"[server] Listening on {addrs}")
        async with server:
            await server.serve_forever()

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        client_ip = peer[0] if peer else "unknown"
        print(f"[connect] {client_ip}")

        try:
            while True:
                line = await reader.readline()
                if not line:
                    break

                payload = line.decode(errors="replace").strip()
                if not payload:
                    continue

                ack = self._process_payload(payload, client_ip)
                writer.write((json.dumps(ack) + "\n").encode())
                await writer.drain()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"[error] Client {client_ip}: {exc}")
        finally:
            print(f"[disconnect] {client_ip}")
            writer.close()
            await writer.wait_closed()

    def _process_payload(self, payload: str, client_ip: str) -> dict[str, Any]:
        now_iso = datetime.now(timezone.utc).isoformat()

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return {
                "status": "error",
                "message": "Invalid JSON payload",
                "server_received_at": now_iso,
            }

        error = self._validate(data)
        if error:
            return {
                "status": "error",
                "message": error,
                "server_received_at": now_iso,
            }

        reading = Reading(
            device_id=str(data["device_id"]),
            moisture_raw=int(data["moisture_raw"]),
            moisture_percent=float(data["moisture_percent"]),
            sensor_pin=int(data["sensor_pin"]) if data.get("sensor_pin") is not None else None,
            firmware_version=(
                str(data["firmware_version"])
                if data.get("firmware_version") is not None
                else None
            ),
            client_timestamp=(
                str(data["timestamp"]) if data.get("timestamp") is not None else None
            ),
            server_received_at=now_iso,
            client_ip=client_ip,
        )

        self._insert(reading)

        print(
            "[reading] "
            f"device={reading.device_id} "
            f"raw={reading.moisture_raw} "
            f"pct={reading.moisture_percent:.2f} "
            f"ip={reading.client_ip}"
        )

        return {
            "status": "ok",
            "message": "Reading accepted",
            "server_received_at": now_iso,
        }

    @staticmethod
    def _validate(data: dict[str, Any]) -> str | None:
        required = ("device_id", "moisture_raw", "moisture_percent")
        missing = [field for field in required if field not in data]
        if missing:
            return f"Missing required field(s): {', '.join(missing)}"

        try:
            moisture_raw = int(data["moisture_raw"])
            moisture_percent = float(data["moisture_percent"])
        except (TypeError, ValueError):
            return "moisture_raw must be int and moisture_percent must be float"

        if moisture_raw < 0:
            return "moisture_raw cannot be negative"

        if not 0.0 <= moisture_percent <= 100.0:
            return "moisture_percent must be in range 0 to 100"

        return None

    def _insert(self, reading: Reading) -> None:
        self._db.execute(
            """
            INSERT INTO readings (
                device_id,
                moisture_raw,
                moisture_percent,
                sensor_pin,
                firmware_version,
                client_timestamp,
                server_received_at,
                client_ip
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reading.device_id,
                reading.moisture_raw,
                reading.moisture_percent,
                reading.sensor_pin,
                reading.firmware_version,
                reading.client_timestamp,
                reading.server_received_at,
                reading.client_ip,
            ),
        )
        self._db.commit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Multi-client soil moisture TCP ingestion server"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Server host bind address")
    parser.add_argument("--port", type=int, default=9000, help="Server port")
    parser.add_argument(
        "--db",
        default="data/readings.db",
        help="Path to SQLite database file",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    server = SoilMoistureServer(args.host, args.port, db_path)

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\n[server] Shutdown requested")


if __name__ == "__main__":
    main()
