# HiveSoil - Multi-Client Server Architecture Demo

This project demonstrates a **multi-client server architecture** for soil moisture monitoring.

- **Server**: Python asynchronous TCP server (handles many concurrent clients).
- **Clients**:
  - ESP32 C++ firmware for real sensor hardware.
  - Optional Python simulator that emulates many devices for testing/demo.

## Architecture

1. ESP32 clients connect to the server over Wi-Fi and TCP.
2. Each client sends newline-delimited JSON payloads with moisture data.
3. The Python server validates, acknowledges, and stores readings in SQLite.
4. Stored data can be inspected from the command line.

## Project Structure

- `server/`: Python ingestion and persistence backend
- `client/esp32/`: ESP32 C++ firmware (`soil_moisture_client.ino`)
- `client/simulator/`: Python multi-client simulator

## Quick Start

### 1) Start server

```bash
cd server
python src/server.py --host 0.0.0.0 --port 9000 --db data/readings.db
```

### 2) Run simulator (optional, proves multi-client behavior quickly)

```bash
cd client/simulator
python multi_client_simulator.py --host 127.0.0.1 --port 9000 --clients 5 --interval 3
```

### 3) Inspect stored readings

```bash
cd server
python src/inspect_readings.py --db data/readings.db --limit 20
```

### 4) Flash ESP32 client

Open `client/esp32/soil_moisture_client.ino` in Arduino IDE, set your:

- Wi-Fi SSID/password
- server host IP and port
- sensor calibration values (`SENSOR_DRY`, `SENSOR_WET`)

Then upload to ESP32.

## Notes

- The server expects one JSON reading per line.
- Use unique `device_id` values for each ESP32 board.
- For LAN testing, ensure firewall allows inbound TCP on server port (`9000` by default).
