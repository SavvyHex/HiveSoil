#!/usr/bin/env python3
"""Inspect the latest persisted readings from SQLite."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show latest soil moisture readings")
    parser.add_argument("--db", default="data/readings.db", help="Path to SQLite DB")
    parser.add_argument("--limit", type=int, default=20, help="Rows to display")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = Path(args.db)

    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        """
        SELECT
            id,
            device_id,
            moisture_raw,
            moisture_percent,
            server_received_at,
            client_ip
        FROM readings
        ORDER BY id DESC
        LIMIT ?
        """,
        (args.limit,),
    )

    rows = cursor.fetchall()
    if not rows:
        print("No readings found.")
        return

    print("id | device_id | raw | percent | server_received_at | client_ip")
    print("-" * 80)
    for row in rows:
        print(" | ".join(str(value) for value in row))


if __name__ == "__main__":
    main()
