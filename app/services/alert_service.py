from sqlalchemy.orm import Session
from app.models import Alert, Notification, Prediction, SensorData
from datetime import datetime


ALERT_MESSAGES = {
    "Waspada": "Kualitas air mendekati batas berbahaya. Segera periksa kolam.",
    "Kritis":  "KRITIS: Kualitas air berbahaya! Tindakan segera diperlukan.",
}

NOTIF_TITLES = {
    "Waspada": "⚠️ Peringatan Kualitas Air",
    "Kritis":  "🚨 KRITIS: Kualitas Air Berbahaya",
}


def process_and_save(
    db: Session,
    sensor: SensorData,
    pred_result: dict
) -> dict:
    """
    Fungsi utama setelah prediksi AI selesai.
    
    Alur:
    1. Simpan prediction ke DB
    2. Jika Waspada/Kritis → buat alert
    3. Buat notification dari alert
    4. Return semua hasil untuk dipakai publisher MQTT

    Dipanggil dari:
    - subscriber.py (data dari MQTT)
    - router sensor_data.py (data dari POST manual)
    """

    # ── 1. Simpan Prediction ──────────────────────────────────
    prediction = Prediction(
        sensor_data_id = sensor.id,
        status         = pred_result["status"],
        confidence     = pred_result["confidence"],
        prob_normal    = pred_result["prob_normal"],
        prob_waspada   = pred_result["prob_waspada"],
        prob_kritis    = pred_result["prob_kritis"],
        urgency        = pred_result["urgency"],
        model_version  = pred_result["model_version"],
    )
    db.add(prediction)
    db.flush()  # dapat prediction.id tanpa commit dulu

    alert        = None
    notification = None

    # ── 2. Buat Alert jika Waspada atau Kritis ────────────────
    if pred_result["status"] in ("Waspada", "Kritis"):
        alert = Alert(
            sensor_data_id = sensor.id,
            prediction_id  = prediction.id,
            level          = pred_result["status"],
            message        = ALERT_MESSAGES[pred_result["status"]],
            action         = pred_result["action"],
            status         = "active",
        )
        db.add(alert)
        db.flush()  # dapat alert.id

        # ── 3. Buat Notification ──────────────────────────────
        notification = Notification(
            alert_id = alert.id,
            title    = NOTIF_TITLES[pred_result["status"]],
            message  = (
                f"{ALERT_MESSAGES[pred_result['status']]} "
                f"(Confidence: {pred_result['confidence']}%) "
                f"Aksi: {pred_result['action']}"
            ),
            is_read  = False,
        )
        db.add(notification)

    db.commit()

    return {
        "prediction":   prediction,
        "alert":        alert,
        "notification": notification,
        "need_actuator_action": pred_result["status"] == "Kritis",
    }