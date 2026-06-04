# 🐟 Backend NILA — Aquaculture IoT Backend

Backend FastAPI untuk sistem monitoring kualitas air budidaya ikan Nila secara real-time, dilengkapi AI prediction (Random Forest), MQTT integration, dan manajemen siklus budidaya.

## 📋 Fitur Utama

- **Sensor Monitoring** — Terima data TDS, pH, DO, suhu, turbiditas via MQTT atau REST
- **AI Prediction** — Klasifikasi kondisi air: Normal / Waspada / Kritis (Random Forest)
- **Actuator Control** — Kendali aerator, pompa via MQTT command
- **Alert & Notifikasi** — Alert otomatis berdasarkan prediksi AI
- **User Management** — Auth JWT, profil pengguna
- **Farming Cycle** — Manajemen siklus tebar benih hingga panen
- **Feed Management** — Stok pakan, jadwal, dan riwayat pemberian makan
- **ML Module** — Prediksi panen dan rekomendasi pakan

## 🚀 Quick Start

### 1. Clone & Setup Environment
```bash
git clone <repo-url>
cd backend-nila

python -m venv venv
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate

pip install -r requirements.txt
```

### 2. Konfigurasi
```bash
cp .env.example .env
# Edit .env sesuai konfigurasi database dan MQTT kamu
```

### 3. Setup Database
```bash
# Buat database PostgreSQL bernama nilaiot_db
# Jalankan migrasi:
psql -U postgres -d nilaiot_db -f init_db.sql
psql -U postgres -d nilaiot_db -f migrations_add_user_features.sql
```

### 4. Jalankan Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Akses Dokumentasi API
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 📡 MQTT Topics

| Topic | Arah | Payload |
|-------|------|---------|
| `aqua/sensor/data` | ESP32 → Backend | `{device_id, temperature, dissolved_oxygen, ph, turbidity, tds}` |
| `aqua/actuator/command` | Backend → ESP32 | `{device, action, triggered_by}` |
| `aqua/actuator/status` | ESP32 → Backend | `{device, is_active}` |
| `aqua/alert` | Backend → App | `{status, urgency, action, confidence}` |

## 🧠 AI Model

- **Algoritma**: Random Forest Classifier
- **Input Features**: Temperature, Dissolved Oxygen, pH, Turbidity, Hour, DayOfWeek, Month
- **Output**: Normal / Waspada / Kritis + confidence score
- **Fallback**: Rule-based jika model `.pkl` tidak ditemukan
- **Retrain**: `python ml/train_model.py`

## 📁 Struktur Proyek

```
backend-nila/
├── app/
│   ├── main.py              # Entry point FastAPI
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── database.py          # DB connection & session
│   ├── mqtt/                # MQTT client, publisher, subscriber
│   ├── routers/             # Endpoint handlers per modul
│   └── services/            # Business logic
├── ml/
│   ├── models/              # .pkl files (RF, scaler, encoder)
│   ├── train_model.py       # Script retrain model
│   └── Monteria_Aquaculture_Data.xlsx  # Training data
├── init_db.sql              # Schema awal
├── migrations_add_user_features.sql  # Migrasi user management
├── requirements.txt
└── .env.example
```

## ⚠️ Catatan Keamanan (Production)

- [ ] Ganti `SECRET_KEY` dengan nilai random yang kuat
- [ ] Set `DEBUG=False`
- [ ] Batasi `CORS_ORIGINS` ke domain frontend kamu (jangan `*`)
- [ ] Gunakan MQTT broker dengan autentikasi (bukan HiveMQ public)
- [ ] Simpan `.env` di server, jangan pernah di-commit ke Git

## 📄 Dokumentasi Lengkap

- [API Documentation](./API_DOCUMENTATION.md)
- [Deployment Checklist](./DEPLOYMENT_CHECKLIST.md)
- [Panduan Indonesia](./PANDUAN_LENGKAP_INDONESIA.md)
