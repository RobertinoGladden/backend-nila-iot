import joblib
import numpy as np
import pandas as pd
import os
from datetime import datetime

MODEL_PATH   = os.getenv("AI_MODEL_PATH",   "ml/models/rf_classifier.pkl")
SCALER_PATH  = os.getenv("AI_SCALER_PATH",  "ml/models/scaler.pkl")
ENCODER_PATH = os.getenv("AI_ENCODER_PATH", "ml/models/label_encoder.pkl")
MODEL_VERSION = "RF-v1"

# Cache model di memory — load sekali saat startup
_model   = None
_scaler  = None
_encoder = None

ACTIONS = {
    "Normal":  "Kondisi kolam baik. Lanjutkan monitoring rutin.",
    "Waspada": "Periksa aerator. Pertimbangkan penggantian air 20-30%.",
    "Kritis":  "SEGERA: Aktifkan aerator darurat, kurangi pakan, periksa sumber pencemaran.",
}

URGENCY = {
    "Normal":  "low",
    "Waspada": "medium",
    "Kritis":  "high",
}


def load_model() -> bool:
    """
    Load model RF dari file .pkl ke memory.
    Dipanggil sekali saat startup FastAPI.
    Return True jika berhasil, False jika gagal.
    """
    global _model, _scaler, _encoder
    try:
        _model   = joblib.load(MODEL_PATH)
        _scaler  = joblib.load(SCALER_PATH)
        _encoder = joblib.load(ENCODER_PATH)
        print(f"✅ AI Model loaded: {MODEL_PATH}")
        return True
    except FileNotFoundError as e:
        print(f"⚠️  Model tidak ditemukan: {e}")
        print("⚠️  Menggunakan rule-based fallback")
        return False
    except Exception as e:
        print(f"❌ Gagal load model: {e}")
        return False


def _rule_based_predict(
    tds: float,
    ph: float,
    do_level: float,
    temperature: float,
    turbidity: float
) -> dict:
    """
    Fallback rule-based jika model .pkl belum ada.
    Threshold berdasarkan standar budidaya ikan nila.
    """
    is_critical = (
        do_level    < 4.0  or
        temperature > 29.5 or
        ph          < 7.0  or
        ph          > 8.5  or
        turbidity   > 4.8
    )
    is_warning = (
        do_level    < 5.0  or
        temperature > 28.5 or
        ph          < 7.3  or
        ph          > 8.1  or
        turbidity   > 4.0
    )

    if is_critical:
        status = "Kritis"
    elif is_warning:
        status = "Waspada"
    else:
        status = "Normal"

    return {
        "status":      status,
        "confidence":  85.0,
        "prob_normal":  100.0 if status == "Normal"  else 0.0,
        "prob_waspada": 100.0 if status == "Waspada" else 0.0,
        "prob_kritis":  100.0 if status == "Kritis"  else 0.0,
        "urgency":     URGENCY[status],
        "action":      ACTIONS[status],
        "model_version": "rule-based-v1",
    }


def predict(
    tds: float,
    ph: float,
    do_level: float,
    temperature: float,
    turbidity: float = 0.0
) -> dict:
    """
    Fungsi utama prediksi kualitas air.
    Dipanggil dari subscriber MQTT dan router /predict.

    Return dict berisi:
        status, confidence, prob_*, urgency, action, model_version
    """
    # Jika probe DO tidak tersedia (0 atau negatif), estimasi dari variabel lain
    if do_level <= 0:
        do_level = calculate_do_estimate(temperature, ph, tds, turbidity)

    # Gunakan rule-based jika model belum di-load
    if _model is None or _encoder is None:
        return _rule_based_predict(tds, ph, do_level, temperature, turbidity)

    try:
        now = datetime.now()

        # Susun feature vector sesuai urutan training
        # [Temperature, Dissolved_Oxygen, pH, Turbidity, Hour, DayOfWeek, Month]
        features = pd.DataFrame([[
            temperature,
            do_level,
            ph,
            turbidity,
            now.hour,
            now.weekday(),
            now.month,
        ]], columns=["Temperature", "Dissolved_Oxygen", "pH", "Turbidity", "Hour", "DayOfWeek", "Month"])

        # Predict
        pred_idx = _model.predict(features)[0]
        status   = _encoder.inverse_transform([pred_idx])[0]
        proba    = _model.predict_proba(features)[0]

        # Map probabilitas ke nama kelas
        prob_map = {
            cls: round(float(p) * 100, 2)
            for cls, p in zip(_encoder.classes_, proba)
        }

        return {
            "status":       status,
            "confidence":   round(float(proba.max()) * 100, 2),
            "prob_normal":  prob_map.get("Normal",  0.0),
            "prob_waspada": prob_map.get("Waspada", 0.0),
            "prob_kritis":  prob_map.get("Kritis",  0.0),
            "urgency":      URGENCY[status],
            "action":       ACTIONS[status],
            "model_version": MODEL_VERSION,
        }

    except Exception as e:
        print(f"❌ Predict error: {e}, fallback ke rule-based")
        return _rule_based_predict(tds, ph, do_level, temperature, turbidity)

def calculate_do_estimate(
    temperature: float,
    ph: float,
    tds: float,
    turbidity: float,
) -> float:
    """
    Estimasi Dissolved Oxygen (mg/L) dari 4 sensor yang sudah ada.

    Digunakan saat probe DO fisik tidak tersedia atau sebagai cross-check.
    Berdasarkan persamaan Benson-Krause (1984) untuk saturasi DO air tawar,
    dimodifikasi dengan faktor koreksi pH, TDS, dan turbidity.

    Bobot kontribusi:
        Suhu      : 45%  (dominan — hubungan terbalik via DO_sat)
        pH        : 25%  (optimal 7.5, turun 3% per unit deviasi)
        TDS       : 20%  (salinitas mengurangi kelarutan O2)
        Turbidity : 10%  (air keruh hambat fotosintesis alga)

    Returns:
        float: DO estimasi dalam mg/L, diclamp antara 0 dan 14.
    """
    T = temperature

    # Benson-Krause: DO saturasi berdasarkan suhu (air tawar, 1 atm)
    do_sat = 14.62 - 0.3898 * T + 0.006969 * (T ** 2) - 0.00005896 * (T ** 3)

    # Faktor koreksi pH — optimal pH=7.5, turun 3% per unit deviasi
    ph_factor = 1.0 - 0.03 * abs(ph - 7.5)
    ph_factor = max(0.5, ph_factor)  # floor 50% untuk pH ekstrem

    # Faktor koreksi TDS — air asin kurang melarutkan O2
    tds_factor = 1.0 - (tds / 50000.0)
    tds_factor = max(0.5, tds_factor)  # floor 50%

    # Faktor koreksi turbidity — air keruh hambat fotosintesis
    ntu_factor = max(0.0, 1.0 - turbidity / 100.0)

    # Kombinasi berbobot
    do_est = do_sat * (0.45 + 0.25 * ph_factor + 0.20 * tds_factor + 0.10 * ntu_factor)

    # Clamp ke rentang fisik valid [0, 14] mg/L
    return max(0.0, min(14.0, round(do_est, 2)))
