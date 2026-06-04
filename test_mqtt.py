"""
NILA IoT — Sensor Simulator
============================
Simulasi ESP32 mengirim data sensor ke HiveMQ MQTT Broker.
Railway backend subscribe ke broker yang sama → proses AI → simpan DB.

Cara pakai:
    pip install paho-mqtt
    python test_mqtt.py

Opsi mode:
    python test_mqtt.py              → mode AUTO (rotasi Normal→Waspada→Kritis)
    python test_mqtt.py --mode normal  → loop Normal terus menerus
    python test_mqtt.py --mode kritis  → kirim skenario Kritis terus
    python test_mqtt.py --interval 3   → kirim setiap 3 detik (default 5)
"""

import paho.mqtt.client as mqtt
import json
import time
import random
import argparse
import socket
from datetime import datetime

# ── Konfigurasi MQTT ─────────────────────────────────────────
BROKER_HOST = "broker.hivemq.com"
PORT        = 1883
TOPIC       = "aqua/sensor/data"
CLIENT_ID   = f"nila-simulator-{random.randint(1000, 9999)}"

# Force IPv4 — paho-mqtt gagal connect jika resolve IPv6
def resolve_ipv4(hostname: str) -> str:
    try:
        ip = socket.getaddrinfo(hostname, PORT, socket.AF_INET)[0][4][0]
        return ip
    except Exception:
        return hostname

BROKER = resolve_ipv4(BROKER_HOST)

# ── Skenario sensor ───────────────────────────────────────────
SCENARIOS = {
    "normal": {
        "label": "✅ Normal",
        "color": "\033[92m",
        "base":  {"temperature": 27.5, "dissolved_oxygen": 6.8, "ph": 7.8,  "turbidity": 3.1, "tds": 450.0},
        "noise": {"temperature": 0.3,  "dissolved_oxygen": 0.15,"ph": 0.08, "turbidity": 0.2, "tds": 15.0},
    },
    "waspada": {
        "label": "⚠️  Waspada",
        "color": "\033[93m",
        "base":  {"temperature": 29.0, "dissolved_oxygen": 5.2, "ph": 8.3,  "turbidity": 4.5, "tds": 370.0},
        "noise": {"temperature": 0.4,  "dissolved_oxygen": 0.2, "ph": 0.1,  "turbidity": 0.3, "tds": 20.0},
    },
    "kritis": {
        "label": "🚨 Kritis",
        "color": "\033[91m",
        "base":  {"temperature": 31.0, "dissolved_oxygen": 3.5, "ph": 8.8,  "turbidity": 5.5, "tds": 280.0},
        "noise": {"temperature": 0.5,  "dissolved_oxygen": 0.3, "ph": 0.12, "turbidity": 0.4, "tds": 25.0},
    },
}

RESET = "\033[0m"
BOLD  = "\033[1m"
CYAN  = "\033[96m"
GRAY  = "\033[90m"

AUTO_ROTATION = ["normal","normal","normal","waspada","waspada","kritis","kritis"]


def build_payload(scenario_key: str, device_id: str = "sensor-01") -> dict:
    s = SCENARIOS[scenario_key]
    b, n = s["base"], s["noise"]
    return {
        "device_id":        device_id,
        "temperature":      round(b["temperature"]      + random.uniform(-n["temperature"],      n["temperature"]),      2),
        "dissolved_oxygen": round(b["dissolved_oxygen"] + random.uniform(-n["dissolved_oxygen"], n["dissolved_oxygen"]), 2),
        "ph":               round(b["ph"]               + random.uniform(-n["ph"],               n["ph"]),               2),
        "turbidity":        round(b["turbidity"]        + random.uniform(-n["turbidity"],        n["turbidity"]),        3),
        "tds":              round(b["tds"]              + random.uniform(-n["tds"],              n["tds"]),              1),
    }


def print_payload(count: int, scenario_key: str, payload: dict):
    s  = SCENARIOS[scenario_key]
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n{BOLD}[#{count:04d}] {ts}{RESET}  {s['color']}{s['label']}{RESET}")
    print(f"  {GRAY}device_id       :{RESET} {payload['device_id']}")
    print(f"  {CYAN}temperature     :{RESET} {payload['temperature']} °C")
    print(f"  {CYAN}dissolved_oxygen:{RESET} {payload['dissolved_oxygen']} mg/L")
    print(f"  {CYAN}ph              :{RESET} {payload['ph']}")
    print(f"  {CYAN}turbidity       :{RESET} {payload['turbidity']} NTU")
    print(f"  {CYAN}tds             :{RESET} {payload['tds']} ppm")


def simulate(mode: str, interval: int, device_id: str):
    try:
        from paho.mqtt.enums import CallbackAPIVersion
        client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION1,
            client_id=CLIENT_ID,
            clean_session=True,
        )
    except ImportError:
        client = mqtt.Client(client_id=CLIENT_ID, clean_session=True)

    connected = [False]

    def on_connect(c, userdata, flags, rc):
        if rc == 0:
            connected[0] = True
            print(f"{BOLD}✅ Terhubung!{RESET} {BROKER_HOST} ({BROKER}:{PORT})")
            print(f"   Topic  : {TOPIC}")
            print(f"   Client : {CLIENT_ID}\n")
        else:
            print(f"❌ Gagal connect rc={rc}")

    client.on_connect = on_connect

    print(f"\n{BOLD}NILA IoT Sensor Simulator{RESET}")
    print(f"Mode     : {mode}")
    print(f"Interval : {interval} detik")
    print(f"Device   : {device_id}")
    print(f"Broker   : {BROKER_HOST} → {BROKER}:{PORT}")
    print(f"Topic    : {TOPIC}")
    print(f"\nMenghubungkan...")

    client.connect(BROKER, PORT, keepalive=60)
    client.loop_start()

    for _ in range(20):
        if connected[0]:
            break
        time.sleep(0.5)
    else:
        print("❌ Timeout connect. Cek koneksi internet.")
        client.loop_stop()
        return

    count = 0
    try:
        while True:
            if mode == "auto":
                scenario_key = AUTO_ROTATION[count % len(AUTO_ROTATION)]
            elif mode in SCENARIOS:
                scenario_key = mode
            else:
                scenario_key = "normal"

            payload = build_payload(scenario_key, device_id)
            print_payload(count + 1, scenario_key, payload)

            result = client.publish(TOPIC, json.dumps(payload), qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"  {GRAY}→ Terkirim ✓{RESET}")
            else:
                print(f"  ❌ Gagal rc={result.rc}")

            count += 1
            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n\n{BOLD}Simulator dihentikan.{RESET} Total terkirim: {count} data\n")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NILA IoT Sensor Simulator")
    parser.add_argument("--mode",     choices=["auto","normal","waspada","kritis"], default="auto")
    parser.add_argument("--interval", type=int,  default=5)
    parser.add_argument("--device",   type=str,  default="sensor-01")
    args = parser.parse_args()
    simulate(args.mode, args.interval, args.device)
