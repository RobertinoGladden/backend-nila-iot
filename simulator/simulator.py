"""
NILA IoT — Sensor Simulator Worker (Railway Service)
=====================================================
Simulasi lengkap ESP32 + 5 sensor kolam budidaya ikan nila.
Mensimulasikan kondisi real: Normal → degradasi → Waspada → Kritis → recovery.

Sensor yang disimulasikan (sesuai sistem nyata):
  - Suhu        : DS18B20 / Analog  (20–35 °C)
  - pH          : Probe Analog      (6.5–9.0)
  - DO          : O₂ Probe Analog   (3–10 mg/L)
  - TDS         : Probe Analog      (ppm / salinitas)
  - Turbidity   : Optical NTU

Aktuator yang dipantau (logika dari bagan sistem):
  - Heater  : aktif jika suhu < 25°C
  - Aerator : aktif jika DO < 5 mg/L
  - Feeder  : jadwal setiap 12 jam

Environment variables:
  MQTT_BROKER_HOST       (default: broker.hivemq.com)
  MQTT_BROKER_PORT       (default: 1883)
  MQTT_TOPIC_SENSOR      (default: aqua/sensor/data)
  MQTT_USERNAME          (opsional, untuk broker private)
  MQTT_PASSWORD          (opsional)
  SIM_MODE               : auto | normal | waspada | kritis | siklus
  SIM_INTERVAL           : detik antar publish (default: 5)
  SIM_DEVICE             : device_id (default: sensor-01)
  SIM_LOG_LEVEL          : verbose | normal | minimal (default: normal)
"""

import paho.mqtt.client as mqtt
import json
import time
import random
import socket
import os
import math
from datetime import datetime

# ══════════════════════════════════════════════════════════════
# KONFIGURASI
# ══════════════════════════════════════════════════════════════

BROKER_HOST  = os.getenv("MQTT_BROKER_HOST",  "broker.hivemq.com")
PORT         = int(os.getenv("MQTT_BROKER_PORT", 1883))
TOPIC        = os.getenv("MQTT_TOPIC_SENSOR",  "aqua/sensor/data")
MQTT_USER    = os.getenv("MQTT_USERNAME",      "")
MQTT_PASS    = os.getenv("MQTT_PASSWORD",      "")
MODE         = os.getenv("SIM_MODE",           "siklus")   # default: siklus realistis
INTERVAL     = int(os.getenv("SIM_INTERVAL",   5))
DEVICE_ID    = os.getenv("SIM_DEVICE",         "sensor-01")
LOG_LEVEL    = os.getenv("SIM_LOG_LEVEL",      "normal")
CLIENT_ID    = f"nila-sim-{random.randint(1000, 9999)}"


# ══════════════════════════════════════════════════════════════
# PARAMETER SENSOR — RANGE NORMAL IKAN NILA
# ══════════════════════════════════════════════════════════════

# Batas optimal kolam nila
OPTIMAL = {
    "temperature":      {"min": 25.0, "max": 30.0, "ideal": 27.5},
    "ph":               {"min": 6.5,  "max": 8.5,  "ideal": 7.5},
    "dissolved_oxygen": {"min": 5.0,  "max": 9.0,  "ideal": 7.0},
    "tds":              {"min": 300,  "max": 600,   "ideal": 450},
    "turbidity":        {"min": 1.0,  "max": 5.0,  "ideal": 3.0},
}

# Batas aktuator (dari bagan sistem)
ACTUATOR_RULES = {
    "heater":  lambda t, do, ph, tds, turb: t < 25.0,
    "aerator": lambda t, do, ph, tds, turb: do < 5.0,
    # feeder: jadwal 12 jam (simulasi berdasarkan jam)
    "feeder":  lambda: datetime.now().hour in [6, 18],
}

# Definisi skenario
SCENARIOS = {
    # ── Normal: semua parameter optimal ──────────────────────
    "normal": {
        "label":       "✅ Normal",
        "color":       "\033[92m",
        "temperature": {"base": 27.5, "noise": 0.3,  "drift": 0.0},
        "ph":          {"base": 7.5,  "noise": 0.05, "drift": 0.0},
        "dissolved_oxygen": {"base": 7.0, "noise": 0.15, "drift": 0.0},
        "tds":         {"base": 450,  "noise": 12,   "drift": 0.0},
        "turbidity":   {"base": 3.0,  "noise": 0.15, "drift": 0.0},
    },

    # ── Waspada: mulai mendekati batas ───────────────────────
    "waspada": {
        "label":       "⚠️  Waspada",
        "color":       "\033[93m",
        "temperature": {"base": 29.5, "noise": 0.4,  "drift": 0.0},
        "ph":          {"base": 8.1,  "noise": 0.08, "drift": 0.0},
        "dissolved_oxygen": {"base": 5.3, "noise": 0.2, "drift": 0.0},
        "tds":         {"base": 370,  "noise": 18,   "drift": 0.0},
        "turbidity":   {"base": 4.3,  "noise": 0.25, "drift": 0.0},
    },

    # ── Kritis: parameter berbahaya bagi ikan ────────────────
    "kritis": {
        "label":       "🚨 Kritis",
        "color":       "\033[91m",
        "temperature": {"base": 31.5, "noise": 0.5,  "drift": 0.0},
        "ph":          {"base": 8.8,  "noise": 0.1,  "drift": 0.0},
        "dissolved_oxygen": {"base": 3.5, "noise": 0.3, "drift": 0.0},
        "tds":         {"base": 270,  "noise": 22,   "drift": 0.0},
        "turbidity":   {"base": 5.8,  "noise": 0.4,  "drift": 0.0},
    },

    # ── Suhu rendah: heater aktif ─────────────────────────────
    "suhu_rendah": {
        "label":       "🌡️  Suhu Rendah",
        "color":       "\033[96m",
        "temperature": {"base": 23.0, "noise": 0.4,  "drift": 0.0},
        "ph":          {"base": 7.5,  "noise": 0.05, "drift": 0.0},
        "dissolved_oxygen": {"base": 7.5, "noise": 0.15, "drift": 0.0},
        "tds":         {"base": 440,  "noise": 10,   "drift": 0.0},
        "turbidity":   {"base": 3.0,  "noise": 0.15, "drift": 0.0},
    },

    # ── DO rendah: aerator aktif ──────────────────────────────
    "do_rendah": {
        "label":       "💧 DO Rendah",
        "color":       "\033[94m",
        "temperature": {"base": 28.0, "noise": 0.3,  "drift": 0.0},
        "ph":          {"base": 7.6,  "noise": 0.05, "drift": 0.0},
        "dissolved_oxygen": {"base": 3.8, "noise": 0.2, "drift": 0.0},
        "tds":         {"base": 450,  "noise": 10,   "drift": 0.0},
        "turbidity":   {"base": 4.0,  "noise": 0.2,  "drift": 0.0},
    },
}

# ── Siklus realistis: simulasi 1 hari kolam (rotasi bertahap) ─
SIKLUS_HARIAN = [
    # (skenario, jumlah_sample) — total ~35 sample = ~3 menit di interval 5s
    ("normal",      5),   # kondisi pagi baik
    ("waspada",     3),   # mulai naik suhu siang
    ("kritis",      3),   # puncak kondisi buruk
    ("waspada",     2),   # recovery
    ("normal",      4),   # kembali normal
    ("do_rendah",   3),   # malam DO turun
    ("normal",      3),   # aerator bantu, DO naik lagi
    ("suhu_rendah", 3),   # malam suhu turun
    ("normal",      4),   # pagi lagi
    ("waspada",     2),
    ("kritis",      2),
    ("normal",      3),
]


# ══════════════════════════════════════════════════════════════
# GENERATOR PAYLOAD
# ══════════════════════════════════════════════════════════════

# State untuk simulasi sinusoidal (lebih realistis)
_sim_tick = 0

def build_payload(scenario_key: str) -> dict:
    """
    Buat payload sensor dengan noise + variasi sinusoidal.
    Mensimulasikan fluktuasi sensor real (bukan nilai statis).
    """
    global _sim_tick
    sc = SCENARIOS[scenario_key]
    _sim_tick += 1

    def val(key):
        cfg   = sc[key]
        base  = cfg["base"]
        noise = cfg["noise"]
        # Tambah komponen sinusoidal kecil untuk realisme
        sine  = math.sin(_sim_tick * 0.3) * noise * 0.4
        rand  = random.uniform(-noise, noise)
        return base + rand + sine

    t    = round(val("temperature"),      2)
    ph   = round(val("ph"),               2)
    do   = round(val("dissolved_oxygen"), 2)
    tds  = round(val("tds"),              1)
    turb = round(abs(val("turbidity")),   3)

    # Clamp ke range fisik sensor
    t    = max(15.0, min(40.0, t))
    ph   = max(4.0,  min(10.0, ph))
    do   = max(0.5,  min(12.0, do))
    tds  = max(50,   min(1200, tds))
    turb = max(0.0,  min(15.0, turb))

    # Evaluasi aktuator berdasarkan nilai sensor
    heater_on  = ACTUATOR_RULES["heater"](t, do, ph, tds, turb)
    aerator_on = ACTUATOR_RULES["aerator"](t, do, ph, tds, turb)
    feeder_on  = ACTUATOR_RULES["feeder"]()

    return {
        "device_id":        DEVICE_ID,
        "temperature":      t,
        "ph":               ph,
        "dissolved_oxygen": do,
        "tds":              tds,
        "turbidity":        turb,
        # Info aktuator (opsional, untuk monitoring)
        "_actuator": {
            "heater":  heater_on,
            "aerator": aerator_on,
            "feeder":  feeder_on,
        },
        "_scenario":   scenario_key,
        "_tick":       _sim_tick,
        "_timestamp":  datetime.now().isoformat(),
    }


def get_water_quality_hint(payload: dict) -> str:
    """Evaluasi sederhana kualitas air dari payload."""
    t   = payload["temperature"]
    ph  = payload["ph"]
    do  = payload["dissolved_oxygen"]
    issues = []
    if t > 30:   issues.append(f"suhu tinggi({t}°C)")
    if t < 25:   issues.append(f"suhu rendah({t}°C)")
    if ph > 8.5: issues.append(f"pH basa({ph})")
    if ph < 6.5: issues.append(f"pH asam({ph})")
    if do < 5:   issues.append(f"DO rendah({do}mg/L)")
    return ", ".join(issues) if issues else "semua parameter OK"


# ══════════════════════════════════════════════════════════════
# SIKLUS ROTASI
# ══════════════════════════════════════════════════════════════

class SiklusIterator:
    """Iterator siklus harian — rotasi bertahap antar skenario."""
    def __init__(self):
        self._phase = 0        # index dalam SIKLUS_HARIAN
        self._count = 0        # berapa kali sudah di phase ini
        self._total = 0        # total publish sejak start

    def next_scenario(self) -> str:
        sc_key, jumlah = SIKLUS_HARIAN[self._phase]
        self._count  += 1
        self._total  += 1
        if self._count >= jumlah:
            self._count  = 0
            self._phase  = (self._phase + 1) % len(SIKLUS_HARIAN)
        return sc_key

_siklus = SiklusIterator()

AUTO_ROTATION = [
    "normal", "normal", "normal",
    "waspada", "waspada",
    "kritis", "kritis",
]

def get_scenario(count: int) -> str:
    if MODE == "siklus":
        return _siklus.next_scenario()
    elif MODE == "auto":
        return AUTO_ROTATION[count % len(AUTO_ROTATION)]
    elif MODE in SCENARIOS:
        return MODE
    return "normal"


# ══════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════

def log(count: int, scenario_key: str, payload: dict, status: str):
    sc = SCENARIOS[scenario_key]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if LOG_LEVEL == "minimal":
        print(f"[{ts}] #{count:05d} {sc['label']:12s} | {status}")
        return

    act = payload.get("_actuator", {})
    hint = get_water_quality_hint(payload)

    if LOG_LEVEL == "verbose":
        print(f"\n{'─'*60}")
        print(f"  [{ts}] #{count:05d}  {sc['label']}")
        print(f"{'─'*60}")
        print(f"  Suhu        : {payload['temperature']:6.2f} °C")
        print(f"  pH          : {payload['ph']:6.2f}")
        print(f"  DO          : {payload['dissolved_oxygen']:6.2f} mg/L")
        print(f"  TDS         : {payload['tds']:6.1f} ppm")
        print(f"  Turbidity   : {payload['turbidity']:6.3f} NTU")
        print(f"  Heater      : {'ON  🔥' if act.get('heater')  else 'OFF'}")
        print(f"  Aerator     : {'ON  ○'  if act.get('aerator') else 'OFF'}")
        print(f"  Feeder      : {'ON  ⚙'  if act.get('feeder')  else 'OFF'}")
        print(f"  Evaluasi    : {hint}")
        print(f"  Publish     : {status}")
    else:
        # normal
        act_str = " ".join([
            "🔥" if act.get("heater")  else "·",
            "○"  if act.get("aerator") else "·",
            "⚙"  if act.get("feeder")  else "·",
        ])
        print(
            f"[{ts}] #{count:05d} {sc['label']:14s} | "
            f"T={payload['temperature']:5.1f} DO={payload['dissolved_oxygen']:4.1f} "
            f"pH={payload['ph']:4.2f} TDS={payload['tds']:5.0f} NTU={payload['turbidity']:4.2f} | "
            f"Akt[{act_str}] | {status}"
        )


# ══════════════════════════════════════════════════════════════
# MQTT
# ══════════════════════════════════════════════════════════════

def resolve_ipv4(hostname: str) -> str:
    """Force IPv4 — paho-mqtt gagal jika resolve ke IPv6."""
    try:
        return socket.getaddrinfo(hostname, PORT, socket.AF_INET)[0][4][0]
    except Exception:
        return hostname


def create_client() -> mqtt.Client:
    try:
        from paho.mqtt.enums import CallbackAPIVersion
        client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION1,
            client_id=CLIENT_ID,
            clean_session=True,
        )
    except ImportError:
        client = mqtt.Client(client_id=CLIENT_ID, clean_session=True)

    if MQTT_USER and MQTT_PASS:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    return client


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    broker_ip = resolve_ipv4(BROKER_HOST)

    print("=" * 65)
    print("  NILA IoT Sensor Simulator — Railway Worker")
    print("=" * 65)
    print(f"  Broker   : {BROKER_HOST}  →  {broker_ip}:{PORT}")
    print(f"  Topic    : {TOPIC}")
    print(f"  Mode     : {MODE}")
    print(f"  Interval : {INTERVAL} detik")
    print(f"  Device   : {DEVICE_ID}")
    print(f"  Log      : {LOG_LEVEL}")
    print(f"  Client   : {CLIENT_ID}")
    print("=" * 65)
    print()
    print("  Kolom output: timestamp | #seq | status | T | DO | pH | TDS | NTU | Aktuator | result")
    print()

    client    = create_client()
    connected = [False]

    def on_connect(c, userdata, flags, rc):
        if rc == 0:
            connected[0] = True
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ MQTT Connected → {broker_ip}:{PORT}\n")
        else:
            codes = {1:"wrong protocol",2:"bad client id",3:"server unavail",4:"bad credentials",5:"not authorized"}
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Connect failed: {codes.get(rc, f'rc={rc}')}")

    def on_disconnect(c, userdata, rc):
        connected[0] = False
        if rc != 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Disconnected rc={rc}, akan reconnect...")

    def on_publish(c, userdata, mid):
        pass  # silent

    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_publish    = on_publish
    client.reconnect_delay_set(min_delay=2, max_delay=30)

    # Connect dengan retry loop
    while True:
        try:
            client.connect(broker_ip, PORT, keepalive=60)
            break
        except Exception as e:
            print(f"Connect error: {e} — retry 5s...")
            time.sleep(5)

    client.loop_start()

    # Tunggu connected (max 10 detik)
    for _ in range(20):
        if connected[0]:
            break
        time.sleep(0.5)
    else:
        print("❌ Timeout: tidak bisa connect ke MQTT broker.")
        client.loop_stop()
        return

    # ── Main publish loop ─────────────────────────────────────
    count          = 0
    total_ok       = 0
    total_fail     = 0
    session_start  = datetime.now()

    try:
        while True:
            scenario_key = get_scenario(count)
            payload_full = build_payload(scenario_key)

            # Payload yang dikirim ke backend (tanpa field _internal)
            payload_send = {k: v for k, v in payload_full.items()
                            if not k.startswith("_")}

            if connected[0]:
                result = client.publish(TOPIC, json.dumps(payload_send), qos=1)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    status = "✓ sent"
                    total_ok += 1
                else:
                    status = f"✗ rc={result.rc}"
                    total_fail += 1
            else:
                status = "⚠ skip(disconnected)"
                total_fail += 1

            log(count + 1, scenario_key, payload_full, status)

            # Stats setiap 50 publish
            if (count + 1) % 50 == 0:
                elapsed = (datetime.now() - session_start).seconds // 60
                print(f"\n  📊 Stats: {count+1} publish | OK:{total_ok} FAIL:{total_fail} | uptime:{elapsed}m\n")

            count += 1
            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        elapsed = (datetime.now() - session_start).seconds
        print(f"\n{'='*65}")
        print(f"  Simulator dihentikan")
        print(f"  Total publish : {count}")
        print(f"  Sukses        : {total_ok}")
        print(f"  Gagal         : {total_fail}")
        print(f"  Uptime        : {elapsed}s")
        print(f"{'='*65}\n")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
