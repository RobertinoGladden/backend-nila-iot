import json
from app.database import SessionLocal
from app.services.ai_service import predict
from app.services.alert_service import process_and_save
from app.services.actuator_service import trigger_by_ai, update_status_from_mqtt
from app.mqtt.publisher import publish_alert
from app.mqtt.client import TOPIC_SENSOR, TOPIC_ACTUATOR_STATUS
from app.models import SensorData
from datetime import datetime


def on_message(client, userdata, message):
    """
    Handler utama semua pesan MQTT masuk.
    Dipanggil otomatis oleh paho-mqtt di background thread.

    Topic yang dihandle:
    - aqua/sensor/data       → proses data sensor
    - aqua/actuator/status   → update status aktuator dari hardware
    """
    try:
        topic   = message.topic
        payload = json.loads(message.payload.decode("utf-8"))
        print(f"\n📥 MQTT [{topic}]: {payload}")

        if topic == TOPIC_SENSOR:
            _handle_sensor_data(payload)

        elif topic == TOPIC_ACTUATOR_STATUS:
            _handle_actuator_status(payload)

        else:
            print(f"⚠️  Topic tidak dikenal: {topic}")

    except json.JSONDecodeError:
        print(f"❌ Payload bukan JSON: {message.payload}")
    except Exception as e:
        print(f"❌ Error handle MQTT message: {e}", exc_info=True)


def _handle_sensor_data(payload: dict):
    """
    Proses data sensor dari MQTT.

    Alur lengkap:
    1. Parse payload dari sensor hardware
    2. Simpan ke tabel sensor_data
    3. Jalankan prediksi AI (RF model)
    4. Simpan prediction + buat alert + notification jika perlu
    5. Trigger aktuator otomatis jika Kritis
    6. Publish alert balik ke MQTT

    Format payload dari RPi/ESP32:
    {
        "device_id":        "sensor-01",
        "temperature":      27.5,
        "dissolved_oxygen": 6.8,
        "ph":               7.8,
        "turbidity":        3.1,
        "tds":              450.0
    }
    """
    db = SessionLocal()
    try:
        # ── 1. Parse nilai sensor ─────────────────────────────
        device_id   = payload.get("device_id",        "sensor-01")
        temperature = float(payload.get("temperature",       payload.get("Temperature",      27.0)))
        do_level    = float(payload.get("dissolved_oxygen",  payload.get("Dissolved_Oxygen",  6.5)))
        ph          = float(payload.get("ph",                payload.get("pH",               7.8)))
        turbidity   = float(payload.get("turbidity",         payload.get("Turbidity",        3.0)))
        tds         = float(payload.get("tds",               payload.get("TDS",              450.0)))

        print(f"   Sensor → T={temperature} DO={do_level} pH={ph} Turb={turbidity} TDS={tds}")

        # ── 2. Simpan ke DB ───────────────────────────────────
        sensor = SensorData(
            device_id   = device_id,
            tds         = tds,
            ph          = ph,
            do_level    = do_level,
            temperature = temperature,
            turbidity   = turbidity,
        )
        db.add(sensor)
        db.flush()  # dapat sensor.id

        # ── 3. Prediksi AI ────────────────────────────────────
        pred_result = predict(
            tds         = tds,
            ph          = ph,
            do_level    = do_level,
            temperature = temperature,
            turbidity   = turbidity,
        )
        print(f"   AI → {pred_result['status']} ({pred_result['confidence']}%)")

        # ── 4. Simpan prediction + alert + notification ───────
        result = process_and_save(
            db          = db,
            sensor      = sensor,
            pred_result = pred_result,
        )

        # ── 5. Trigger aktuator jika Kritis/Waspada ──────────
        if result["alert"] is not None:
            trigger_by_ai(
                db       = db,
                status   = pred_result["status"],
                alert_id = result["alert"].id,
            )

            # ── 6. Publish alert balik ke MQTT ────────────────
            publish_alert(
                status     = pred_result["status"],
                urgency    = pred_result["urgency"],
                action     = pred_result["action"],
                confidence = pred_result["confidence"],
            )

    except Exception as e:
        db.rollback()
        print(f"❌ Error handle sensor data: {e}")
    finally:
        db.close()


def _handle_actuator_status(payload: dict):
    """
    Update status aktuator dari feedback hardware.

    Format payload dari RPi/ESP32:
    {
        "device":    "aerator",
        "is_active": true
    }
    """
    db = SessionLocal()
    try:
        device_name = payload.get("device")
        is_active   = bool(payload.get("is_active", False))

        if not device_name:
            print("❌ Payload actuator status tidak ada field 'device'")
            return

        update_status_from_mqtt(
            db          = db,
            device_name = device_name,
            is_active   = is_active,
        )

    except Exception as e:
        db.rollback()
        print(f"❌ Error handle actuator status: {e}")
    finally:
        db.close()