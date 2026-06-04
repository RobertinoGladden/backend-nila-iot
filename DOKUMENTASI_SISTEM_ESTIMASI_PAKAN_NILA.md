# Dokumentasi Sistem Estimasi Pakan — Backend NILA IoT

> Versi dokumen: 2.0 (biomass-based) | Diperbarui: Mei 2026  
> Repositori: `RobertinoGladden/backend-nila-iot`

---

## Daftar Isi

1. [Gambaran Umum Sistem](#1-gambaran-umum-sistem)
2. [Arsitektur & Struktur Database](#2-arsitektur--struktur-database)
3. [Alur Kerja Lengkap](#3-alur-kerja-lengkap)
4. [Modul: Siklus Budidaya (Farming Cycle)](#4-modul-siklus-budidaya-farming-cycle)
5. [Modul: Estimasi Biomassa](#5-modul-estimasi-biomassa)
6. [Modul: Rekomendasi Pakan (recommend_feeding)](#6-modul-rekomendasi-pakan-recommend_feeding)
7. [Modul: Manajemen Stok & Histori Pakan](#7-modul-manajemen-stok--histori-pakan)
8. [Modul: Prediksi Panen (Harvest Estimation)](#8-modul-prediksi-panen-harvest-estimation)
9. [Studi Kasus: 100 kg Bibit Ikan Nila](#9-studi-kasus-100-kg-bibit-ikan-nila)
10. [Panduan Migrasi Database](#10-panduan-migrasi-database)
11. [Panduan Deploy ke Railway](#11-panduan-deploy-ke-railway)
12. [Keterbatasan & Rencana Pengembangan](#12-keterbatasan--rencana-pengembangan)
13. [Referensi Parameter Budidaya Nila](#13-referensi-parameter-budidaya-nila)

---

## 1. Gambaran Umum Sistem

Backend NILA IoT adalah sistem monitoring dan manajemen budidaya ikan Nila berbasis IoT yang dibangun menggunakan **FastAPI** dan **PostgreSQL**, di-deploy di **Railway**. Sistem ini menggabungkan:

- **Monitoring real-time** — data sensor kualitas air (suhu, DO, pH, TDS, turbiditas) dikirim dari ESP32 via MQTT
- **AI/ML prediksi kondisi air** — Random Forest Classifier mengklasifikasikan kondisi menjadi Normal / Waspada / Kritis
- **Sistem estimasi pakan** — menghitung rekomendasi pakan harian berdasarkan biomassa ikan dan kondisi air aktual
- **Prediksi panen** — estimasi tanggal panen berdasarkan kualitas air dan pertumbuhan ikan

### Komponen Utama

```
ESP32 (Sensor)
    ↓ MQTT
Backend FastAPI (Railway)
    ↓
PostgreSQL (Railway)
    ↓
Aplikasi Mobile / Dashboard
```

### File yang Relevan untuk Sistem Pakan

| File | Fungsi |
|------|--------|
| `app/models.py` | Definisi tabel database (SQLAlchemy ORM) |
| `app/schemas.py` | Validasi input/output API (Pydantic) |
| `app/services/farming_service.py` | Logika siklus budidaya dan kalkulasi biomassa |
| `app/services/ml_service.py` | Logika rekomendasi pakan dan prediksi panen |
| `app/services/feed_service.py` | Manajemen stok pakan, jadwal, dan histori |
| `app/routers/farming_cycle.py` | Endpoint API siklus budidaya |
| `app/routers/feed.py` | Endpoint API manajemen pakan |
| `app/routers/ml.py` | Endpoint API ML (rekomendasi dan prediksi) |
| `migrations_seed_biomass.sql` | Migrasi database untuk fitur biomassa |

---

## 2. Arsitektur & Struktur Database

### Tabel yang Terlibat dalam Sistem Pakan

```
users
  └── farming_cycles          ← Siklus budidaya (DIPERLUAS dengan data bibit)
        ├── feed_stock         ← Stok pakan saat ini
        │     └── feed_transactions  ← Riwayat masuk/keluar pakan
        ├── feeding_schedule   ← Jadwal pemberian pakan
        ├── feeding_history    ← Realisasi aktual pemberian pakan
        ├── feeding_recommendations  ← Output rekomendasi ML
        └── harvest_predictions      ← Prediksi tanggal panen
```

### Skema Tabel `farming_cycles` (Versi Terbaru)

```sql
CREATE TABLE farming_cycles (
    id                      SERIAL PRIMARY KEY,
    user_id                 INTEGER NOT NULL REFERENCES users(id),
    cycle_name              VARCHAR(255),
    seeding_date            DATE NOT NULL,
    estimated_harvest_date  DATE,
    actual_harvest_date     DATE,
    status                  VARCHAR(20) DEFAULT 'active',

    -- Kolom baru (versi 2.0) --
    seed_weight_kg          FLOAT,          -- Total berat bibit (kg)
    fish_count_estimated    INTEGER,        -- Estimasi jumlah ekor
    avg_seed_weight_g       FLOAT DEFAULT 10.0,   -- Berat rata-rata 1 bibit (gram)
    feed_rate_percent       FLOAT DEFAULT 3.0,    -- Feed rate % dari biomassa/hari
    target_harvest_weight_g FLOAT DEFAULT 300.0,  -- Target berat panen per ekor (gram)
    survival_rate_percent   FLOAT DEFAULT 85.0,   -- Estimasi survival rate (%)

    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);
```

### Skema Tabel `feeding_recommendations`

```sql
CREATE TABLE feeding_recommendations (
    id                   SERIAL PRIMARY KEY,
    farming_cycle_id     INTEGER NOT NULL REFERENCES farming_cycles(id),
    recommended_quantity FLOAT NOT NULL,   -- Dalam KG
    recommended_time     TIME,             -- Waktu rekomendasi (default 07:00)
    reasoning            TEXT,             -- Penjelasan teks lengkap
    confidence_score     FLOAT,            -- Skor kepercayaan 0-100
    ml_model_id          INTEGER REFERENCES ml_models(id),
    features_used        JSONB,            -- Snapshot fitur yang digunakan
    recommendation_date  TIMESTAMP DEFAULT NOW(),
    created_at           TIMESTAMP DEFAULT NOW()
);
```

### Skema Tabel `feed_stock`

```sql
CREATE TABLE feed_stock (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id),
    farming_cycle_id  INTEGER REFERENCES farming_cycles(id),
    current_quantity  FLOAT DEFAULT 0,   -- Stok saat ini (kg)
    unit              VARCHAR(50) DEFAULT 'kg',
    min_threshold     FLOAT,             -- Batas minimum stok (alert)
    updated_at        TIMESTAMP DEFAULT NOW()
);
```

---

## 3. Alur Kerja Lengkap

### Saat Memulai Siklus Baru

```
1. Pengguna membuat farming cycle baru (POST /farming-cycle/)
   → Input: tanggal tebar, berat bibit, berat rata-rata bibit, feed rate, dll.
   → Sistem otomatis menghitung fish_count_estimated
   → Stok pakan kosong (0 kg) dibuat otomatis

2. Pengguna menambahkan stok pakan (POST /feed/{stock_id}/transaction)
   → Input: jumlah kg pakan yang dibeli
   → Stok bertambah di feed_stock

3. Pengguna membuat jadwal makan (POST /feed/farming-cycle/{id}/schedule)
   → Input: jam makan, kuantitas expected, frekuensi
```

### Saat Operasional Harian

```
4. Sensor ESP32 mengirim data kualitas air via MQTT
   → Backend menyimpan ke sensor_data
   → AI mengklasifikasikan kondisi air (Normal/Waspada/Kritis)
   → Alert otomatis dikirim jika kondisi berbahaya

5. Sistem/pengguna memanggil rekomendasi pakan (POST /ml/farming-cycle/{id}/feeding-recommendation)
   → extract_feeding_features() mengambil data sensor 7 hari terakhir
   → recommend_feeding() menghitung kuantitas pakan berbasis biomassa
   → Hasil disimpan ke feeding_recommendations

6. Pengguna mencatat realisasi pemberian pakan (POST /feed/farming-cycle/{id}/feeding)
   → Disimpan ke feeding_history
   → Stok pakan berkurang otomatis via feed_transactions
```

### Saat Panen

```
7. Sistem membuat prediksi tanggal panen (POST /ml/farming-cycle/{id}/harvest-estimate)
   → estimate_harvest_date() menganalisis kualitas air historis
   → Hasil disimpan ke harvest_predictions

8. Pengguna menutup siklus (PUT /farming-cycle/{id})
   → actual_harvest_date diisi
   → Status diubah menjadi "completed"
```

---

## 4. Modul: Siklus Budidaya (Farming Cycle)

### API Endpoint

**Membuat siklus budidaya baru:**

```http
POST /farming-cycle/
Authorization: Bearer <token>
Content-Type: application/json

{
    "cycle_name": "Kolam A - Batch 1",
    "seeding_date": "2025-05-01",
    "seed_weight_kg": 100,
    "avg_seed_weight_g": 10.0,
    "feed_rate_percent": 3.0,
    "target_harvest_weight_g": 300.0,
    "survival_rate_percent": 85.0
}
```

**Response:**

```json
{
    "id": 1,
    "cycle_name": "Kolam A - Batch 1",
    "seeding_date": "2025-05-01",
    "status": "active",
    "seed_weight_kg": 100.0,
    "fish_count_estimated": 10000,
    "avg_seed_weight_g": 10.0,
    "feed_rate_percent": 3.0,
    "target_harvest_weight_g": 300.0,
    "survival_rate_percent": 85.0
}
```

### Penjelasan Field

| Field | Tipe | Wajib | Default | Keterangan |
|-------|------|-------|---------|------------|
| `seed_weight_kg` | float | Tidak | null | Total berat bibit yang ditebar. Jika diisi, sistem akan menghitung `fish_count_estimated` secara otomatis |
| `avg_seed_weight_g` | float | Tidak | 10.0 | Rata-rata berat 1 ekor bibit dalam gram. Bibit nila umum ~5–15g |
| `feed_rate_percent` | float | Tidak | 3.0 | Persentase biomassa yang diberikan sebagai pakan per hari. Standar nila: 3–5% |
| `target_harvest_weight_g` | float | Tidak | 300.0 | Target berat per ekor saat panen. Nila siap jual biasanya 200–400g |
| `survival_rate_percent` | float | Tidak | 85.0 | Estimasi persentase ikan yang bertahan hidup selama siklus |

### Kalkulasi `fish_count_estimated`

```python
# farming_service.py
if cycle_data.seed_weight_kg and cycle_data.avg_seed_weight_g:
    fish_count_estimated = int(
        (cycle_data.seed_weight_kg * 1000) / cycle_data.avg_seed_weight_g
    )

# Contoh: 100 kg bibit, rata-rata 10g/ekor
# fish_count_estimated = (100 * 1000) / 10 = 10.000 ekor
```

### Mendapatkan Statistik Siklus

```http
GET /farming-cycle/{cycle_id}/stats
```

**Response mencakup:**

```json
{
    "cycle_id": 1,
    "farming_days": 45,
    "seed_weight_kg": 100.0,
    "fish_count_estimated": 10000,
    "current_biomass_kg": 1317.5,
    "feed_rate_percent": 3.0,
    "survival_rate_percent": 85.0,
    "total_feeding_events": 45,
    "total_feed_quantity": 850.2
}
```

---

## 5. Modul: Estimasi Biomassa

Biomassa adalah total berat ikan yang hidup di kolam pada satu waktu tertentu. Ini adalah **dasar perhitungan pakan** yang paling akurat.

### Rumus Estimasi Pertumbuhan

Sistem menggunakan model pertumbuhan **linear sederhana**:

```
Berat per ekor (hari ke-N) = berat_bibit_g + (pertumbuhan_per_hari × N)

Pertumbuhan per hari = (target_panen_g - berat_bibit_g) / total_hari_siklus
                     = (300 - 10) / 90
                     = 3.22 gram/hari
```

### Rumus Biomassa

```
Ikan bertahan  = fish_count_estimated × (survival_rate / 100)
Biomassa (kg)  = (ikan_bertahan × berat_per_ekor_g) / 1000
```

### Contoh Perhitungan (100 kg bibit, hari ke-45)

```
Bibit awal      : 10.000 ekor
Survival 85%    : 8.500 ekor bertahan
Berat hari ke-45: 10 + (3.22 × 45) = 154.9 gram/ekor
Biomassa        : (8.500 × 154.9) / 1000 = 1.316.7 kg
```

### Implementasi di Kode

```python
# ml_service.py — di dalam recommend_feeding()

total_days = 90
growth_per_day = (target_g - avg_seed_g) / total_days
current_weight_g = avg_seed_g + (growth_per_day * min(farming_days, total_days))
current_weight_g = max(current_weight_g, avg_seed_g)

surviving_fish = int(fish_count * survival_rate)
biomass_kg = (surviving_fish * current_weight_g) / 1000
```

---

## 6. Modul: Rekomendasi Pakan (recommend_feeding)

Ini adalah fungsi inti sistem estimasi pakan. Lokasi: `app/services/ml_service.py`

### Formula Lengkap

```
Pakan (kg/hari) = Biomassa (kg) × Feed Rate (%) × Faktor Suhu × Faktor DO × Faktor Tahap
```

### Langkah 1: Tentukan Kuantitas Dasar

```python
base_quantity_kg = biomass_kg * feed_rate_pct

# Contoh: biomassa 1.317 kg, feed rate 3%
# base_quantity_kg = 1.317 × 0.03 = 39.5 kg/hari
```

Jika data bibit tidak diisi (`seed_weight_kg` kosong), sistem menggunakan **fallback**:
```python
base_quantity_kg = 0.004  # 4 gram per ekor (estimasi kasar)
```

### Langkah 2: Faktor Koreksi Suhu

Suhu air berpengaruh langsung pada nafsu makan ikan Nila.

| Kondisi | Range | Faktor | Alasan |
|---------|-------|--------|--------|
| Dingin | < 20°C | ×0.70 | Metabolisme lambat, nafsu makan turun 30% |
| Sejuk | 20–25°C | ×0.85 | Belum optimal |
| Optimal | 25–30°C | ×1.00 | Kondisi terbaik untuk makan |
| Panas | > 30°C | ×0.80 | Stres panas, nafsu makan berkurang |

```python
if temp < 20:
    temp_factor = 0.70
elif temp < 25:
    temp_factor = 0.85
elif temp <= 30:
    temp_factor = 1.00
else:
    temp_factor = 0.80
```

### Langkah 3: Faktor Koreksi DO (Dissolved Oxygen)

Kadar oksigen terlarut sangat kritis. Ikan tidak akan makan normal jika DO rendah.

| Kondisi | Range | Faktor | Alasan |
|---------|-------|--------|--------|
| Kritis | < 4 mg/L | ×0.60 | Ikan stres berat, kurangi 40% pakan |
| Rendah | 4–5 mg/L | ×0.80 | Nafsu makan berkurang |
| Optimal | ≥ 5 mg/L | ×1.00 | Kondisi normal |

```python
if do_level < 4:
    do_factor = 0.60
elif do_level < 5:
    do_factor = 0.80
else:
    do_factor = 1.00
```

> **Catatan penting:** Saat DO < 4 mg/L, aktifkan aerator segera. Jangan memberi pakan berlebih karena pakan yang tidak dimakan akan memperburuk kualitas air.

### Langkah 4: Faktor Tahap Budidaya

Kebutuhan pakan relatif terhadap biomassa berubah sesuai tahap pertumbuhan.

| Tahap | Range | Faktor | Alasan |
|-------|-------|--------|--------|
| Awal | 0–29 hari | ×0.70 | Bibit masih adaptasi, porsi kecil |
| Pertumbuhan | 30–59 hari | ×1.00 | Fase makan maksimal |
| Pra-panen | ≥ 60 hari | ×0.85 | Pertumbuhan melambat, efisiensi pakan menurun |

```python
if farming_days < 30:
    stage_factor = 0.70
elif farming_days < 60:
    stage_factor = 1.00
else:
    stage_factor = 0.85
```

### Langkah 5: Hitung Rekomendasi Final

```python
total_factor = temp_factor * do_factor * stage_factor
recommended_kg = base_quantity_kg * total_factor
```

**Contoh kondisi optimal (semua faktor 1.0):**
```
Biomassa hari ke-45 : 1.317 kg
Feed rate 3%        : 1.317 × 0.03 = 39.5 kg dasar
Suhu 28°C           : ×1.00
DO 6 mg/L           : ×1.00
Hari ke-45          : ×1.00
──────────────────────────────
Rekomendasi final   : 39.5 kg/hari
```

**Contoh kondisi buruk (DO rendah + suhu dingin):**
```
Biomassa            : 1.317 kg
Feed rate 3%        : 39.5 kg dasar
Suhu 18°C           : ×0.70
DO 3.5 mg/L         : ×0.60
Hari ke-45          : ×1.00
──────────────────────────────
Rekomendasi final   : 39.5 × 0.70 × 0.60 = 16.6 kg/hari
```

### Langkah 6: Confidence Score

```python
has_bio_data = 1 if (fish_count and seed_weight_kg) else 0
sensor_score = min(features["sensor_readings_count"] / 50, 1.0)
confidence = 60 + (has_bio_data * 25) + (sensor_score * 10)
# Min: 60% (tidak ada data bibit + tidak ada sensor)
# Max: 95% (data bibit lengkap + cukup data sensor)
```

| Kondisi | Confidence |
|---------|-----------|
| Tidak ada data bibit, tidak ada sensor | 60% |
| Ada data bibit, tidak ada sensor | 85% |
| Tidak ada data bibit, ada sensor | 70% |
| Data bibit + sensor lengkap | 95% |

### API Endpoint Rekomendasi Pakan

```http
POST /ml/farming-cycle/{cycle_id}/feeding-recommendation
Authorization: Bearer <token>
```

**Response:**

```json
{
    "id": 42,
    "farming_cycle_id": 1,
    "recommended_quantity": 39.525,
    "recommended_time": "07:00:00",
    "reasoning": "Biomassa: 8500 ekor × 155.0g = 1317.5 kg biomassa. Feed rate dasar: 3.0%/hari → 39525.0g. Koreksi: suhu optimal (28°C) →×1.00, DO optimal (6.2 mg/L) →×1.00, tahap pertumbuhan (hari ke-45) →×1.00. Total faktor: ×1.0. Rekomendasi akhir: 39525.0g (39.525 kg).",
    "confidence_score": 95.0,
    "features_used": {
        "farming_days": 45,
        "current_temperature": 28.0,
        "current_do": 6.2,
        "biomass_kg": 1317.5,
        "base_quantity_kg": 39.525,
        "temp_factor": 1.0,
        "do_factor": 1.0,
        "stage_factor": 1.0
    },
    "recommendation_date": "2025-06-15T07:00:00"
}
```

---

## 7. Modul: Manajemen Stok & Histori Pakan

### Menambah Stok Pakan

```http
POST /feed/{stock_id}/transaction
Authorization: Bearer <token>
Content-Type: application/json

{
    "transaction_type": "input",
    "quantity": 500.0,
    "notes": "Pembelian pakan bulan Juni"
}
```

Setelah membeli 100 kg bibit, estimasi kebutuhan pakan total adalah **±3.166 kg** selama 90 hari. Disarankan membeli pakan dalam batch setiap 2–4 minggu sesuai kebutuhan bertahap.

### Mencatat Realisasi Pemberian Pakan

```http
POST /feed/farming-cycle/{cycle_id}/feeding
Authorization: Bearer <token>
Content-Type: application/json

{
    "feeding_schedule_id": 1,
    "quantity_given": 39.5,
    "administered_by": "operator",
    "notes": "Pakan pagi sesuai rekomendasi"
}
```

### Melihat Statistik Pakan

```http
GET /feed/farming-cycle/{cycle_id}/feeding/stats
```

**Response:**

```json
{
    "farming_cycle_id": 1,
    "total_feeding_events": 45,
    "total_feed_quantity": 852.3,
    "average_per_feeding": 18.94,
    "active_schedules": 1
}
```

### Membuat Jadwal Makan

```http
POST /feed/farming-cycle/{cycle_id}/schedule
Authorization: Bearer <token>
Content-Type: application/json

{
    "scheduled_time": "07:00:00",
    "expected_quantity": 39.5,
    "frequency": "daily"
}
```

> **Rekomendasi praktik:** Untuk ikan Nila, idealnya pemberian pakan 2–3 kali sehari (pagi, siang, sore). Sistem saat ini menghasilkan 1 jadwal per rekomendasi — tambahkan jadwal kedua dan ketiga secara manual dengan pembagian porsi, misalnya 40% pagi, 35% siang, 25% sore.

---

## 8. Modul: Prediksi Panen (Harvest Estimation)

### Cara Kerja

Fungsi `estimate_harvest_date()` menghitung tanggal panen berdasarkan **skor kualitas air** historis sejak awal siklus.

```python
# ml_service.py

water_quality_score = (
    (7 - abs(avg_ph - 7)) * 0.3 +          # Bobot pH: 30%
    min(avg_do / 6, 1) * 0.3 +              # Bobot DO: 30%
    (1 - min(abs(avg_tds - 400) / 1000, 1)) * 0.4  # Bobot TDS: 40%
)

remaining_days = int(75 * water_quality_score)
# Skor 1.0 → 75 hari tersisa
# Skor 0.5 → 37 hari tersisa
```

**Interpretasi skor:**
- Skor mendekati 1.0 → kualitas air sangat baik → perlu lebih banyak hari agar ikan tumbuh optimal
- Skor rendah → kualitas air buruk → sistem memperkirakan panen lebih cepat (ikan sulit tumbuh)

### API Endpoint Prediksi Panen

```http
POST /ml/farming-cycle/{cycle_id}/harvest-estimate
Authorization: Bearer <token>
```

**Response:**

```json
{
    "id": 5,
    "farming_cycle_id": 1,
    "predicted_harvest_date": "2025-08-01",
    "confidence_score": 72.5,
    "features_used": {
        "farming_days": 45,
        "avg_ph": 7.1,
        "avg_do": 5.8,
        "avg_tds": 380,
        "avg_temperature": 27.5,
        "total_feed_given": 852.3,
        "sensor_count": 450
    }
}
```

---

## 9. Studi Kasus: 100 kg Bibit Ikan Nila

### Parameter Awal

| Parameter | Nilai | Keterangan |
|-----------|-------|------------|
| Berat total bibit | 100 kg | Input pengguna |
| Berat rata-rata bibit | 10 g/ekor | Bibit nila standar |
| Estimasi jumlah ekor | **10.000 ekor** | Dihitung otomatis: 100.000g ÷ 10g |
| Feed rate | 3%/hari | Standar nila |
| Survival rate | 85% | Estimasi |
| Target panen | 300 g/ekor | Ukuran jual standar |
| Siklus budidaya | 90 hari | ±3 bulan |
| Ikan bertahan hidup | **8.500 ekor** | 10.000 × 85% |

### Proyeksi Pertumbuhan & Kebutuhan Pakan (Kondisi Optimal)

| Hari | Tahap | Berat/ekor | Biomassa | Pakan/hari | Pakan kumulatif |
|------|-------|-----------|---------|-----------|----------------|
| 1 | Awal | 13 g | 113 kg | 2.4 kg | 2.4 kg |
| 7 | Awal | 32 g | 275 kg | 5.8 kg | 30 kg |
| 15 | Awal | 58 g | 496 kg | 10.4 kg | 86 kg |
| 30 | Pertumbuhan | 107 g | 907 kg | 27.2 kg | 261 kg |
| 45 | Pertumbuhan | 155 g | 1.317 kg | 39.5 kg | 708 kg |
| 60 | Pra-panen | 203 g | 1.728 kg | 44.1 kg | 1.372 kg |
| 75 | Pra-panen | 252 g | 2.139 kg | 54.5 kg | 2.207 kg |
| 90 | Pra-panen | 300 g | 2.550 kg | 65.0 kg | 3.166 kg |

### Ringkasan Hasil Akhir

| Metrik | Nilai |
|--------|-------|
| **Total pakan dibutuhkan (90 hari)** | **±3.166 kg** |
| Biomassa awal (bibit) | 100 kg |
| Biomassa akhir (panen) | 2.550 kg |
| Pertambahan biomassa | 2.450 kg |
| FCR (Feed Conversion Ratio) | **1,29** |
| Estimasi jumlah ikan panen | 8.500 ekor |

> **FCR 1,29** berarti setiap 1,29 kg pakan menghasilkan 1 kg daging ikan. Nilai ideal nila adalah 1,2–1,8. Nilai ini tergolong baik.

### Pengaruh Kondisi Air pada Pakan (Hari ke-45)

| Skenario | Suhu | DO | Pakan/hari |
|----------|------|-----|-----------|
| Optimal | 28°C | 6 mg/L | 39.5 kg |
| Suhu dingin | 18°C | 6 mg/L | 27.7 kg |
| DO rendah | 28°C | 3.5 mg/L | 23.7 kg |
| Kondisi buruk | 18°C | 3.5 mg/L | 16.6 kg |

### Contoh Request API Lengkap

**1. Buat siklus dengan 100 kg bibit:**

```bash
curl -X POST https://your-app.railway.app/farming-cycle/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "cycle_name": "Kolam A - Mei 2025",
    "seeding_date": "2025-05-01",
    "seed_weight_kg": 100,
    "avg_seed_weight_g": 10.0,
    "feed_rate_percent": 3.0,
    "target_harvest_weight_g": 300.0,
    "survival_rate_percent": 85.0
  }'
```

**2. Tambah stok pakan awal (beli 500 kg untuk bulan pertama):**

```bash
curl -X POST https://your-app.railway.app/feed/1/transaction \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_type": "input",
    "quantity": 500,
    "notes": "Pembelian awal pakan bulan Mei"
  }'
```

**3. Minta rekomendasi pakan harian:**

```bash
curl -X POST https://your-app.railway.app/ml/farming-cycle/1/feeding-recommendation \
  -H "Authorization: Bearer <token>"
```

---

## 10. Panduan Migrasi Database

Jika sudah ada data sebelumnya di Railway, jalankan file `migrations_seed_biomass.sql`.

### Cara Menjalankan di Railway

**Opsi A — Via Railway CLI:**

```bash
railway connect
psql -f migrations_seed_biomass.sql
```

**Opsi B — Via psql langsung:**

```bash
psql "postgresql://user:password@host:port/database" -f migrations_seed_biomass.sql
```

String koneksi bisa dilihat di Railway → Postgres → Variables → `DATABASE_URL`.

**Opsi C — Salin isi SQL ke Railway Query Editor:**

1. Buka Railway → Postgres → Database tab
2. Klik "Query" atau gunakan tab SQL editor
3. Paste isi file `migrations_seed_biomass.sql`
4. Jalankan

### Isi Migration

```sql
ALTER TABLE farming_cycles
    ADD COLUMN IF NOT EXISTS seed_weight_kg          FLOAT,
    ADD COLUMN IF NOT EXISTS fish_count_estimated    INTEGER,
    ADD COLUMN IF NOT EXISTS avg_seed_weight_g       FLOAT DEFAULT 10.0,
    ADD COLUMN IF NOT EXISTS feed_rate_percent       FLOAT DEFAULT 3.0,
    ADD COLUMN IF NOT EXISTS target_harvest_weight_g FLOAT DEFAULT 300.0,
    ADD COLUMN IF NOT EXISTS survival_rate_percent   FLOAT DEFAULT 85.0;
```

Migration ini **aman dijalankan berulang** (`IF NOT EXISTS`) — tidak akan error jika kolom sudah ada.

---

## 11. Panduan Deploy ke Railway

### File yang Diperbarui (Perlu Di-deploy Ulang)

```
app/models.py                          ← Kolom baru FarmingCycle
app/schemas.py                         ← Field baru di FarmingCycleCreate/Response
app/services/farming_service.py        ← Logika fish_count_estimated + biomassa stats
app/services/ml_service.py             ← recommend_feeding() versi biomassa
migrations_seed_biomass.sql            ← Jalankan SEBELUM deploy
```

### Urutan Deploy yang Benar

```
1. Jalankan migrations_seed_biomass.sql di database Railway
2. Push kode ke GitHub
3. Railway akan auto-deploy (jika Railway terhubung ke GitHub)
   ATAU jalankan: railway up
4. Verifikasi di Swagger: https://your-app.railway.app/docs
```

### Verifikasi Setelah Deploy

Cek endpoint berikut untuk memastikan semuanya bekerja:

```bash
# Cek model sudah punya kolom baru
GET /farming-cycle/active

# Cek rekomendasi pakan bekerja
POST /ml/farming-cycle/{id}/feeding-recommendation
```

---

## 12. Keterbatasan & Rencana Pengembangan

### Keterbatasan Saat Ini

| No. | Keterbatasan | Dampak |
|----|-------------|--------|
| 1 | Pertumbuhan menggunakan model **linear**, bukan kurva pertumbuhan nyata | Estimasi biomassa bisa meleset ±15–20% |
| 2 | Pemberian pakan hanya **1 waktu** (07:00) | Tidak mencerminkan praktik 2–3× sehari |
| 3 | Tidak ada **feedback loop** — histori aktual tidak memperbarui model | Rekomendasi tidak belajar dari data lapangan |
| 4 | Survival rate bersifat **statis** — tidak berubah sepanjang siklus | Kematian mendadak tidak terdeteksi |
| 5 | Model ML untuk rekomendasi pakan adalah **rule-based** (bukan trained ML) | Akurasi terbatas dibanding model terlatih |
| 6 | `fish_count_estimated` tidak diperbarui jika ada penambahan/kematian ikan | Data tidak akurat setelah kejadian luar biasa |

### Rekomendasi Pengembangan

**Jangka pendek:**

- Tambah endpoint untuk update `fish_count_estimated` secara manual (saat ada kematian massal atau penambahan bibit)
- Tambah jadwal makan menjadi multi-waktu (pagi, siang, sore) dengan distribusi porsi
- Tambah field `actual_fish_count` untuk pencatatan sensus ikan berkala

**Jangka menengah:**

- Implementasi model pertumbuhan **Von Bertalanffy** atau **Gompertz** yang lebih akurat
- Bangun feedback loop: jika realisasi pakan (`feeding_history`) secara konsisten di bawah/atas rekomendasi, sesuaikan `feed_rate_percent` otomatis
- Integrasikan data **harga pakan** untuk kalkulasi biaya operasional per hari

**Jangka panjang:**

- Latih model ML sesungguhnya menggunakan data histori dari banyak siklus budidaya
- Tambah fitur **anomaly detection** — jika pola makan ikan berubah drastis, kirim alert
- Integrasi dengan **timbangan digital** untuk bobot ikan aktual (bukan estimasi)

---

## 13. Referensi Parameter Budidaya Nila

### Kualitas Air Optimal

| Parameter | Optimal | Waspada | Kritis |
|-----------|---------|---------|--------|
| Suhu | 25–30°C | 20–25°C atau 30–32°C | < 18°C atau > 35°C |
| DO (Oksigen Terlarut) | ≥ 5 mg/L | 4–5 mg/L | < 4 mg/L |
| pH | 6.5–8.5 | 6.0–6.5 atau 8.5–9.0 | < 6.0 atau > 9.5 |
| TDS | 200–800 ppm | 100–200 atau 800–1500 | < 100 atau > 2000 |
| Turbiditas | 25–40 NTU | 15–25 atau 40–60 | < 10 atau > 100 |

### Parameter Budidaya Standar Nila

| Parameter | Nilai Standar | Keterangan |
|-----------|--------------|------------|
| Padat tebar | 10–30 ekor/m² | Tergantung sistem budidaya |
| Berat bibit | 5–20 g/ekor | Ukuran bibit yang umum digunakan |
| Feed rate | 3–5% biomassa/hari | Turunkan saat mendekati panen |
| FCR ideal | 1.2–1.8 | Feed Conversion Ratio |
| Survival rate | 80–95% | Tergantung manajemen kolam |
| Waktu panen | 3–6 bulan | Tergantung ukuran bibit dan target |
| Berat panen | 200–500 g/ekor | Ukuran jual umum |

### Panduan Feed Rate Berdasarkan Berat Ikan

| Berat Ikan | Feed Rate Anjuran |
|-----------|-------------------|
| < 10 g (bibit) | 5–8%/hari |
| 10–50 g | 4–6%/hari |
| 50–100 g | 3–5%/hari |
| 100–200 g | 3–4%/hari |
| > 200 g | 2–3%/hari |

> Sistem saat ini menggunakan feed rate **tunggal dan tetap** sepanjang siklus. Untuk hasil lebih akurat, pertimbangkan menurunkan `feed_rate_percent` secara manual sesuai tabel di atas setiap 2–3 minggu.

---

*Dokumentasi ini mencakup versi sistem v2.0 (biomass-based). Untuk pertanyaan atau kontribusi, lihat repositori: `RobertinoGladden/backend-nila-iot`.*
