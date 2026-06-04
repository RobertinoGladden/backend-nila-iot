"""
Bootstrap database — jalankan sekali saat startup.
Buat semua tabel dari ORM models + migrate kolom yang missing + seed data awal.
"""
from sqlalchemy import text
from app.database import engine, SessionLocal
from app.models import Base, ActuatorStatus


MIGRATIONS = [
    # ── farming_cycles: kolom baru ──────────────────────────────
    "ALTER TABLE farming_cycles ADD COLUMN IF NOT EXISTS seed_weight_kg          FLOAT",
    "ALTER TABLE farming_cycles ADD COLUMN IF NOT EXISTS fish_count_estimated    INTEGER",
    "ALTER TABLE farming_cycles ADD COLUMN IF NOT EXISTS avg_seed_weight_g       FLOAT DEFAULT 10.0",
    "ALTER TABLE farming_cycles ADD COLUMN IF NOT EXISTS feed_rate_percent       FLOAT DEFAULT 3.0",
    "ALTER TABLE farming_cycles ADD COLUMN IF NOT EXISTS target_harvest_weight_g FLOAT DEFAULT 300.0",
    "ALTER TABLE farming_cycles ADD COLUMN IF NOT EXISTS survival_rate_percent   FLOAT DEFAULT 85.0",

    # ── users: kolom profil ──────────────────────────────────────
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number        VARCHAR(20)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS greenhouse_location VARCHAR(255)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS address             TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_photo_url   VARCHAR",

    # ── feed_stock: kolom baru ───────────────────────────────────
    "ALTER TABLE feed_stock ADD COLUMN IF NOT EXISTS min_threshold     FLOAT",
    "ALTER TABLE feed_stock ADD COLUMN IF NOT EXISTS farming_cycle_id  INTEGER REFERENCES farming_cycles(id) ON DELETE SET NULL",
]


def run():
    print("=== Bootstrap DB ===")

    # 1. Buat semua tabel baru dari ORM (skip jika sudah ada)
    Base.metadata.create_all(bind=engine)
    print("OK  Semua tabel siap")

    # 2. Jalankan migrasi ALTER TABLE untuk kolom yang mungkin belum ada
    with engine.connect() as conn:
        for sql in MIGRATIONS:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception as e:
                # Sebagian besar error di sini tidak fatal (kolom sudah ada, dll)
                print(f"SKIP  {sql[:60]}... => {e}")
    print("OK  Migrasi kolom selesai")

    # 3. Seed aktuator default jika belum ada
    db = SessionLocal()
    try:
        if db.query(ActuatorStatus).count() == 0:
            db.add_all([
                ActuatorStatus(device_name="aerator", is_active=False, mode="auto"),
                ActuatorStatus(device_name="heater",  is_active=False, mode="auto"),
                ActuatorStatus(device_name="pompa",   is_active=False, mode="auto"),
            ])
            db.commit()
            print("OK  Aktuator default di-seed")
        else:
            print("OK  Aktuator sudah ada, skip seed")
    finally:
        db.close()

    print("=== Bootstrap selesai ===")


if __name__ == "__main__":
    run()