# 🚀 NILA IoT — Deploy Guide (Railway.app)

Sistem berjalan **100% cloud** — tidak perlu local, tidak perlu ngrok.

---

## Struktur Project

```
backend-nila-iot/
├── app/                    ← FastAPI backend
│   ├── mqtt/               ← MQTT client & subscriber
│   ├── routers/            ← API endpoints
│   └── services/           ← Business logic & AI
├── ml/models/              ← Random Forest .pkl files
├── simulator/              ← Railway worker: simulasi sensor
│   ├── simulator.py
│   ├── requirements.txt
│   └── railway.toml
├── bootstrap.py            ← Buat tabel DB saat startup
├── railway.toml            ← Config deploy backend
├── test_mqtt.py            ← Script lokal untuk test manual
└── .env.example
```

---

## Alur Sistem

```
[simulator/ di Railway]
        │  publish setiap 5 detik
        ▼
[broker.hivemq.com]  ← MQTT broker publik
        │  subscribe (background)
        ▼
[backend-nila-iot di Railway]
        │
        ├── AI Prediksi (Random Forest)
        ├── Simpan ke PostgreSQL (nilaiot_db)
        ├── Trigger aktuator jika Kritis
        └── REST API → Flutter App
```

---

## Deploy ke Railway

### Step 1 — Push ke GitHub

```bash
git add .
git commit -m "feat: nila iot full stack"
git push -u origin main --force
```

### Step 2 — Deploy Backend

1. [railway.app](https://railway.app) → **New Project** → **GitHub Repo**
2. Pilih repo → Railway detect `railway.toml` otomatis
3. Tambah **PostgreSQL** service di project yang sama
4. Set Variables di service backend (lihat tabel di bawah)
5. Generate Domain → Settings → Networking → Generate Domain

### Step 3 — Deploy Simulator

1. Di canvas Railway → **+** → **GitHub Repository** → repo yang sama
2. **Root Directory** → isi `simulator`
3. Set Variables simulator (lihat tabel di bawah)
4. Deploy

---

## Environment Variables

### Backend Service

| Key | Value |
|-----|-------|
| `DATABASE_URL` | Add Reference → Postgres.DATABASE_URL |
| `SECRET_KEY` | random string 32+ karakter |
| `DEBUG` | `False` |
| `CORS_ORIGINS` | `*` |
| `AI_MODEL_PATH` | `ml/models/rf_classifier.pkl` |
| `AI_SCALER_PATH` | `ml/models/scaler.pkl` |
| `AI_ENCODER_PATH` | `ml/models/label_encoder.pkl` |
| `MQTT_BROKER_HOST` | `broker.hivemq.com` |
| `MQTT_BROKER_PORT` | `1883` |
| `MQTT_CLIENT_ID` | `nilaiot-backend` |
| `MQTT_TOPIC_SENSOR` | `aqua/sensor/data` |
| `MQTT_TOPIC_ACTUATOR_COMMAND` | `aqua/actuator/command` |
| `MQTT_TOPIC_ACTUATOR_STATUS` | `aqua/actuator/status` |
| `MQTT_TOPIC_ALERT` | `aqua/alert` |

### Simulator Service

| Key | Value |
|-----|-------|
| `MQTT_BROKER_HOST` | `broker.hivemq.com` |
| `MQTT_BROKER_PORT` | `1883` |
| `MQTT_TOPIC_SENSOR` | `aqua/sensor/data` |
| `SIM_MODE` | `siklus` (auto/normal/waspada/kritis) |
| `SIM_INTERVAL` | `5` (detik) |
| `SIM_DEVICE` | `sensor-01` |
| `SIM_LOG_LEVEL` | `normal` (verbose/minimal) |

---

## Test Manual (dari PC lokal)

```bash
# Install dependency
pip install paho-mqtt

# Jalankan simulator lokal
python test_mqtt.py

# Mode spesifik
python test_mqtt.py --mode kritis
python test_mqtt.py --mode normal --interval 2
python test_mqtt.py --device sensor-02 --mode waspada
```

---

## Sensor yang Disimulasikan

| Sensor | Range | Hardware |
|--------|-------|----------|
| Suhu | 20–35 °C | DS18B20 / Analog |
| pH | 6.5–9.0 | Probe Analog |
| DO | 3–10 mg/L | O₂ Probe Analog |
| TDS | ppm / salinitas | Probe Analog |
| Turbidity | NTU | Optical |

## Logika Aktuator

| Aktuator | Kondisi Aktif |
|----------|---------------|
| Heater | suhu < 25°C |
| Aerator | DO < 5 mg/L |
| Feeder | jadwal jam 06:00 & 18:00 |

---

## API Docs

Setelah deploy, buka:
```
https://backend-nila-iot-xxxx.up.railway.app/docs
```
