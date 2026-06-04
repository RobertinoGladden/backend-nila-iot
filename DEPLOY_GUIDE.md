# Panduan Deploy Backend NILA IoT ke Fly.io + Supabase

## Arsitektur Baru
ESP32 → broker.hivemq.com:1883 → [Backend Fly.io] ↔ [Supabase PostgreSQL]

---

## LANGKAH 1 — Setup Supabase (Database Gratis)

1. Buka https://supabase.com → Sign up pakai GitHub
2. Klik "New Project" → isi nama project, password DB, pilih region **Southeast Asia (Singapore)**
3. Tunggu project selesai dibuat (~2 menit)
4. Masuk ke **SQL Editor** (sidebar kiri)
5. Jalankan isi file `init_db.sql` → klik Run
6. Jalankan isi file `migrations_add_user_features.sql` → klik Run
7. Ambil connection string:
   - Masuk ke **Settings → Database**
   - Scroll ke bagian **Connection string → URI**
   - Copy string seperti: `postgresql://postgres:[PASSWORD]@db.xxxx.supabase.co:5432/postgres`

---

## LANGKAH 2 — Install Fly CLI

### Windows (PowerShell):
```
powershell -ExecutionPolicy ByPass -c "irm https://fly.io/install.ps1 | iex"
```

### Mac/Linux:
```
curl -L https://fly.io/install.sh | sh
```

---

## LANGKAH 3 — Login & Deploy ke Fly.io

```bash
# Login (buka browser otomatis)
fly auth login

# Masuk ke folder project
cd backend-nila-iot

# Copy file Dockerfile dan fly.toml ke root folder project
# (file sudah disediakan)

# Launch app (pertama kali)
fly launch --no-deploy

# Saat ditanya "Would you like to copy its configuration to the new app?" → ketik: y
# Saat ditanya nama app → ketik: backend-nila-iot (atau nama lain yang kamu mau)
# Saat ditanya region → pilih: sin (Singapore)
# Saat ditanya "Would you like to set up a PostgreSQL database?" → ketik: n (pakai Supabase)

# Set environment variables/secrets
fly secrets set \
  DATABASE_URL="postgresql://postgres:[PASSWORD]@db.xxxx.supabase.co:5432/postgres" \
  SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"

# Deploy!
fly deploy
```

---

## LANGKAH 4 — Cek Status

```bash
# Lihat log
fly logs

# Cek status app
fly status

# Buka di browser
fly open
```

URL backend kamu: `https://backend-nila-iot.fly.dev`
Swagger docs: `https://backend-nila-iot.fly.dev/docs`

---

## LANGKAH 5 — Update Frontend/App

Ganti semua URL yang tadinya mengarah ke Railway dengan URL Fly.io baru:
`https://backend-nila-iot.fly.dev`

---

## Troubleshooting

### Error "could not connect to database"
- Pastikan DATABASE_URL sudah benar
- Cek di Supabase → Settings → Database → Connection string

### MQTT tidak connect
- HiveMQ public broker kadang ada downtime
- Cek log: `fly logs`
- Kalau sering putus, pertimbangkan HiveMQ Cloud free tier (https://www.hivemq.com/mqtt-cloud-broker/)

### App crash saat startup
- Lihat detail error: `fly logs`
- Pastikan semua file ml/models/*.pkl ikut ter-copy (sudah ada di repo)

---

## Catatan Penting

- Fly.io free tier: 3 shared VMs + 160GB bandwidth/bulan
- Supabase free tier: 500MB storage, unlimited API calls
- Keduanya GRATIS dan TIDAK butuh kartu kredit
- `auto_stop_machines = false` di fly.toml memastikan backend tidak pernah sleep
