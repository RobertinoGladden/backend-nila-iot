"""
Training script untuk model Random Forest.
Jalankan file ini SEKALI untuk generate model .pkl
yang akan dipakai oleh FastAPI backend.

Cara jalankan:
    cd nilaiot-backend
    python ml/aquaculture_ai_production.py

Output:
    ml/models/rf_classifier.pkl
    ml/models/scaler.pkl
    ml/models/label_encoder.pkl
"""

import os
import warnings
import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import classification_report, accuracy_score, f1_score

warnings.filterwarnings("ignore")

# ── Konfigurasi Path ──────────────────────────────────────────
# Sesuai struktur folder:
# nilaiot-backend/
# ├── ml/
# │   ├── models/          ← output model
# │   └── aquaculture_ai_production.py  ← file ini

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DATA_PATH    = os.path.join(BASE_DIR, "Monteria_Aquaculture_Data.xlsx")
MODEL_DIR    = os.path.join(BASE_DIR, "models")
MODEL_PATH   = os.path.join(MODEL_DIR, "rf_classifier.pkl")
SCALER_PATH  = os.path.join(MODEL_DIR, "scaler.pkl")
ENCODER_PATH = os.path.join(MODEL_DIR, "label_encoder.pkl")
RANDOM_SEED  = 42

FEATURE_COLS = [
    "Temperature",
    "Dissolved_Oxygen",
    "pH",
    "Turbidity",
    "Hour",
    "DayOfWeek",
    "Month",
]


# ═══════════════════════════════════════════════════════════════
# LABELING
# ═══════════════════════════════════════════════════════════════

def label_water_quality(row: pd.Series) -> str:
    """
    Labeling otomatis berdasarkan threshold domain budidaya nila.
    Prioritas: Kritis > Waspada > Normal
    """
    do   = row["Dissolved_Oxygen"]
    temp = row["Temperature"]
    ph   = row["pH"]
    turb = row["Turbidity"]

    # Kritis
    if (do   < 4.0 or
        temp > 29.5 or
        ph   < 7.0  or
        ph   > 8.5  or
        turb > 4.8):
        return "Kritis"

    # Waspada
    if (do   < 5.0 or
        temp > 28.5 or
        ph   < 7.3  or
        ph   > 8.1  or
        turb > 4.0):
        return "Waspada"

    return "Normal"


# ═══════════════════════════════════════════════════════════════
# FEATURE ENGINEERING
# ═══════════════════════════════════════════════════════════════

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Tambah fitur waktu dari kolom DateTime"""
    df = df.copy()
    df["Hour"]      = pd.to_datetime(df["DateTime"]).dt.hour
    df["DayOfWeek"] = pd.to_datetime(df["DateTime"]).dt.dayofweek
    df["Month"]     = pd.to_datetime(df["DateTime"]).dt.month
    df["Label"]     = df.apply(label_water_quality, axis=1)
    return df


# ═══════════════════════════════════════════════════════════════
# TRAINING
# ═══════════════════════════════════════════════════════════════

def train(df: pd.DataFrame):
    """Training Random Forest dan simpan model ke ml/models/"""

    X  = df[FEATURE_COLS]
    le = LabelEncoder()
    y  = le.fit_transform(df["Label"])

    # Split data 80/20
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size    = 0.2,
        random_state = RANDOM_SEED,
        stratify     = y
    )

    # Scaler
    scaler    = StandardScaler()
    scaler.fit(X_train)  # fit hanya di train

    print("\n" + "═" * 50)
    print("  TRAINING RANDOM FOREST")
    print("═" * 50)
    print(f"  Total data : {len(df):,} baris")
    print(f"  Train      : {len(X_train):,} sampel")
    print(f"  Test       : {len(X_test):,} sampel")
    print(f"\n  Distribusi label:")
    for lbl, cnt in df["Label"].value_counts().items():
        print(f"    {lbl:<10}: {cnt:>5} ({cnt/len(df)*100:.1f}%)")

    # Training Random Forest
    print("\n  Training model...")
    rf = RandomForestClassifier(
        n_estimators = 200,
        max_depth    = None,
        class_weight = "balanced",
        random_state = RANDOM_SEED,
        n_jobs       = -1,
    )
    rf.fit(X_train, y_train)

    # Evaluasi
    rf_pred = rf.predict(X_test)
    rf_acc  = accuracy_score(y_test, rf_pred)
    rf_f1   = f1_score(y_test, rf_pred, average="weighted")
    rf_cv   = cross_val_score(rf, X, y, cv=5, scoring="accuracy", n_jobs=-1)

    print(f"\n  ✅ Akurasi  : {rf_acc * 100:.2f}%")
    print(f"  ✅ F1-Score : {rf_f1:.4f}")
    print(f"  ✅ CV 5-fold: {rf_cv.mean() * 100:.2f}% ± {rf_cv.std() * 100:.2f}%")

    print("\n" + "─" * 50)
    print("  CLASSIFICATION REPORT")
    print("─" * 50)
    print(classification_report(y_test, rf_pred, target_names=le.classes_))

    # Feature importance
    print("─" * 50)
    print("  FEATURE IMPORTANCE")
    print("─" * 50)
    fi = sorted(
        zip(FEATURE_COLS, rf.feature_importances_),
        key=lambda x: x[1],
        reverse=True
    )
    for feat, score in fi:
        bar = "█" * int(score * 50)
        print(f"  {feat:<20}: {score:.4f} {bar}")

    return rf, scaler, le, rf_acc, rf_f1


# ═══════════════════════════════════════════════════════════════
# SIMPAN MODEL
# ═══════════════════════════════════════════════════════════════

def save_models(rf, scaler, le):
    """Simpan model ke ml/models/"""
    os.makedirs(MODEL_DIR, exist_ok=True)

    joblib.dump(rf,     MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    joblib.dump(le,     ENCODER_PATH)

    print("\n" + "═" * 50)
    print("  MODEL TERSIMPAN")
    print("═" * 50)
    for path in [MODEL_PATH, SCALER_PATH, ENCODER_PATH]:
        size_kb = os.path.getsize(path) / 1024
        print(f"  ✅ {path}")
        print(f"     Size: {size_kb:.1f} KB")


# ═══════════════════════════════════════════════════════════════
# DEMO PREDIKSI
# ═══════════════════════════════════════════════════════════════

def demo_predict(rf, scaler, le):
    """
    Demo prediksi setelah training selesai.
    Simulasi data sensor yang akan dikirim dari RPi/ESP32.
    """
    from datetime import datetime

    print("\n" + "═" * 50)
    print("  DEMO PREDIKSI REAL-TIME")
    print("═" * 50)

    demo_data = [
        {
            "label":       "Kondisi Normal",
            "Temperature": 27.5,
            "Dissolved_Oxygen": 6.8,
            "pH":          7.8,
            "Turbidity":   3.1,
        },
        {
            "label":       "Kondisi Waspada",
            "Temperature": 28.8,
            "Dissolved_Oxygen": 5.4,
            "pH":          8.2,
            "Turbidity":   4.2,
        },
        {
            "label":       "Kondisi Kritis",
            "Temperature": 29.8,
            "Dissolved_Oxygen": 3.8,
            "pH":          8.6,
            "Turbidity":   5.1,
        },
    ]

    now = datetime.now()
    icons = {"Normal": "🟢", "Waspada": "🟡", "Kritis": "🔴"}

    for i, sensor in enumerate(demo_data, 1):
        features = np.array([[
            sensor["Temperature"],
            sensor["Dissolved_Oxygen"],
            sensor["pH"],
            sensor["Turbidity"],
            now.hour,
            now.weekday(),
            now.month,
        ]])

        pred_idx   = rf.predict(features)[0]
        status     = le.inverse_transform([pred_idx])[0]
        proba      = rf.predict_proba(features)[0]
        confidence = round(float(proba.max()) * 100, 2)
        prob_map   = {
            cls: round(float(p) * 100, 2)
            for cls, p in zip(le.classes_, proba)
        }

        print(f"\n  [{i}] {sensor['label']}")
        print(f"      Temp={sensor['Temperature']}°C  "
              f"DO={sensor['Dissolved_Oxygen']}mg/L  "
              f"pH={sensor['pH']}  Turb={sensor['Turbidity']}NTU")
        print(f"      Status     : {icons.get(status, '')} {status}")
        print(f"      Confidence : {confidence}%")
        print(f"      Probability: " +
              "  ".join(f"{k}={v}%" for k, v in prob_map.items()))


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║   AI KUALITAS AIR — BUDIDAYA IKAN NILA           ║")
    print("║   Random Forest Training Script                  ║")
    print("╚══════════════════════════════════════════════════╝")

    # ── 1. Load data ──────────────────────────────────────────
    print(f"\n  [1/4] Memuat data dari: {DATA_PATH}")
    if not os.path.exists(DATA_PATH):
        print(f"  ❌ File tidak ditemukan: {DATA_PATH}")
        print("  Pastikan file Excel ada di folder ml/")
        return

    df_raw = pd.read_excel(DATA_PATH, sheet_name="Hourly Data")
    print(f"  ✅ {len(df_raw):,} baris data dimuat")

    # ── 2. Feature engineering + labeling ────────────────────
    print("\n  [2/4] Feature engineering & labeling...")
    df = build_features(df_raw)
    print(f"  ✅ Labeling selesai")

    # ── 3. Training ───────────────────────────────────────────
    print("\n  [3/4] Training model...")
    rf, scaler, le, acc, f1 = train(df)

    # ── 4. Simpan model ───────────────────────────────────────
    print("\n  [4/4] Menyimpan model...")
    save_models(rf, scaler, le)

    # ── Demo prediksi ─────────────────────────────────────────
    demo_predict(rf, scaler, le)

    print("\n" + "═" * 50)
    print("  ✅ SELESAI!")
    print("═" * 50)
    print(f"  Akurasi Final : {acc * 100:.2f}%")
    print(f"  F1-Score      : {f1:.4f}")
    print(f"\n  Model siap dipakai oleh FastAPI backend.")
    print(f"  Jalankan backend dengan:")
    print(f"  → uvicorn app.main:app --reload")
    print("═" * 50 + "\n")


if __name__ == "__main__":
    main()