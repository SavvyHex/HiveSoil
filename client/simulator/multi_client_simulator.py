#!/usr/bin/env python3
"""Simulate multiple sensor clients sending moisture readings to the server."""

from __future__ import annotations

import argparse
import asyncio
import json
import random
from datetime import datetime, timezone


async def run_client(device_id: str, host: str, port: int, interval: float) -> None:
    while True:
        try:
            reader, writer = await asyncio.open_connection(host, port)
            print(f"[{device_id}] connected")

            while True:
                moisture_raw = random.randint(1300, 3200)
                moisture_percent = max(0.0, min(100.0, ((3200 - moisture_raw) / (3200 - 1400)) * 100.0))
                payload = {
                    "device_id": device_id,
                    "moisture_raw": moisture_raw,
                    "moisture_percent": round(moisture_percent, 2),
                    "sensor_pin": 34,
                    "firmware_version": "sim-1.0.0",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                writer.write((json.dumps(payload) + "\n").encode())
                await writer.drain()

                ack_line = await reader.readline()
                if not ack_line:
                    raise ConnectionError("server closed connection")

                print(f"[{device_id}] ack: {ack_line.decode().strip()}")
                await asyncio.sleep(interval)
        except Exception as exc:  # noqa: BLE001
            print(f"[{device_id}] reconnecting after error: {exc}")
            await asyncio.sleep(2)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-client simulator")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--clients", type=int, default=5)
    parser.add_argument("--interval", type=float, default=3.0)
    args = parser.parse_args()

    tasks = [
        asyncio.create_task(run_client(f"sim-{i+1:02d}", args.host, args.port, args.interval))
        for i in range(args.clients)
    ]

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
