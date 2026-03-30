# Client Side

## ESP32 hardware client (C++)

File: `esp32/soil_moisture_client.ino`

### Hardware

- ESP32 board
- Soil moisture sensor analog output -> ESP32 GPIO34 (default in code)
- Common GND between ESP32 and sensor

### Configure before upload

In the sketch, update:

- `WIFI_SSID`
- `WIFI_PASSWORD`
- `SERVER_HOST`
- `SERVER_PORT`
- `DEVICE_ID`
- sensor calibration values (`SENSOR_DRY`, `SENSOR_WET`)

## Optional simulator (Python)

File: `simulator/multi_client_simulator.py`

Use it to generate many virtual clients when only one ESP32 is available.

```bash
cd simulator
python multi_client_simulator.py --host 127.0.0.1 --port 9000 --clients 10 --interval 2
```
