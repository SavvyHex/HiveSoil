# Server (Python)

This folder contains an asynchronous multi-client TCP server for ingesting soil moisture data.

## Features

- Accepts many concurrent ESP32 client connections.
- Expects newline-delimited JSON messages.
- Validates incoming payload fields.
- Persists readings to SQLite (`data/readings.db`).
- Responds with newline-delimited JSON acknowledgements.

## Expected message format

```json
{
  "device_id": "esp32-01",
  "moisture_raw": 2130,
  "moisture_percent": 47.2,
  "sensor_pin": 34,
  "firmware_version": "1.0.0",
  "timestamp": "2026-03-30T10:22:00Z"
}
```

Required fields:

- `device_id` (string)
- `moisture_raw` (integer)
- `moisture_percent` (float from 0 to 100)

## Run

```bash
cd server
python src/server.py --host 0.0.0.0 --port 9000 --db data/readings.db
```

## Inspect stored data

```bash
cd server
python src/inspect_readings.py --db data/readings.db --limit 20
```
