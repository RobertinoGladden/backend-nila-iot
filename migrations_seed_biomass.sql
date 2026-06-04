-- Migration: Tambah kolom data bibit dan feed rate ke farming_cycles
-- Jalankan: psql -U postgres -d nilaiot_db -f migrations_seed_biomass.sql

ALTER TABLE farming_cycles
    ADD COLUMN IF NOT EXISTS seed_weight_kg          FLOAT,
    ADD COLUMN IF NOT EXISTS fish_count_estimated    INTEGER,
    ADD COLUMN IF NOT EXISTS avg_seed_weight_g       FLOAT DEFAULT 10.0,
    ADD COLUMN IF NOT EXISTS feed_rate_percent       FLOAT DEFAULT 3.0,
    ADD COLUMN IF NOT EXISTS target_harvest_weight_g FLOAT DEFAULT 300.0,
    ADD COLUMN IF NOT EXISTS survival_rate_percent   FLOAT DEFAULT 85.0;

-- Update estimasi jumlah ikan untuk data lama yang sudah punya seed_weight_kg
UPDATE farming_cycles
SET fish_count_estimated = FLOOR((seed_weight_kg * 1000) / avg_seed_weight_g)
WHERE seed_weight_kg IS NOT NULL
  AND avg_seed_weight_g IS NOT NULL
  AND avg_seed_weight_g > 0
  AND fish_count_estimated IS NULL;

COMMENT ON COLUMN farming_cycles.seed_weight_kg          IS 'Total berat bibit yang ditebar dalam kg';
COMMENT ON COLUMN farming_cycles.fish_count_estimated    IS 'Estimasi jumlah ekor = (seed_weight_kg * 1000) / avg_seed_weight_g';
COMMENT ON COLUMN farming_cycles.avg_seed_weight_g       IS 'Rata-rata berat 1 ekor bibit dalam gram (default 10g)';
COMMENT ON COLUMN farming_cycles.feed_rate_percent       IS 'Feed rate: persentase dari biomassa yang diberikan sebagai pakan per hari (default 3%)';
COMMENT ON COLUMN farming_cycles.target_harvest_weight_g IS 'Target berat ikan per ekor saat panen dalam gram (default 300g)';
COMMENT ON COLUMN farming_cycles.survival_rate_percent   IS 'Estimasi persentase ikan yang bertahan hidup (default 85%)';
