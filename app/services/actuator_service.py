from sqlalchemy.orm import Session
from app.models import ActuatorStatus, ActuatorLog
from app.mqtt.publisher import publish_actuator_command
from datetime import datetime


ACTUATOR_RULES = {
    "Kritis": {
        "aerator": "on",
        "pompa":   "on",
    },
    "Waspada": {
        "aerator": "on",
    },
}


def control_actuator(
    db: Session,
    device_name: str,
    action: str,
    triggered_by: str = "manual",
    alert_id: int = None
) -> dict:
    """
    Kontrol satu aktuator:
    1. Update status di DB
    2. Catat di log
    3. Publish MQTT ke hardware
    """

    # ── 1. Update status aktuator di DB ──────────────────────
    actuator = db.query(ActuatorStatus).filter(
        ActuatorStatus.device_name == device_name
    ).first()

    if not actuator:
        return {"success": False, "message": f"Device {device_name} tidak ditemukan"}

    actuator.is_active  = (action == "on")
    actuator.updated_at = datetime.now()

    # ── 2. Catat di log ───────────────────────────────────────
    log = ActuatorLog(
        device_name  = device_name,
        action       = action,
        triggered_by = triggered_by,
        alert_id     = alert_id,
    )
    db.add(log)
    db.commit()

    # ── 3. Publish MQTT ke hardware ───────────────────────────
    mqtt_success = publish_actuator_command(
        device_name  = device_name,
        action       = action,
        triggered_by = triggered_by,
    )

    print(f"🔧 Aktuator [{device_name}] → {action} | by={triggered_by} | mqtt={mqtt_success}")

    return {
        "success":     True,
        "device_name": device_name,
        "action":      action,
        "triggered_by": triggered_by,
        "mqtt_sent":   mqtt_success,
    }


def trigger_by_ai(
    db: Session,
    status: str,
    alert_id: int = None
) -> list:
    """
    Trigger aktuator otomatis berdasarkan hasil AI.
    Dipanggil dari alert_service setelah status Waspada/Kritis.

    Return: list hasil kontrol tiap device
    """
    results = []
    rules   = ACTUATOR_RULES.get(status, {})

    for device_name, action in rules.items():
        # Cek mode aktuator — hanya auto yang bisa di-trigger AI
        actuator = db.query(ActuatorStatus).filter(
            ActuatorStatus.device_name == device_name
        ).first()

        if actuator and actuator.mode == "auto":
            result = control_actuator(
                db           = db,
                device_name  = device_name,
                action       = action,
                triggered_by = "ai",
                alert_id     = alert_id,
            )
            results.append(result)
        else:
            print(f"⚠️  {device_name} mode=manual, skip AI trigger")

    return results


def update_status_from_mqtt(db: Session, device_name: str, is_active: bool) -> bool:
    """
    Update status aktuator dari feedback MQTT hardware.
    Dipanggil dari subscriber.py saat RPi/ESP32 konfirmasi status.
    """
    actuator = db.query(ActuatorStatus).filter(
        ActuatorStatus.device_name == device_name
    ).first()

    if not actuator:
        return False

    actuator.is_active  = is_active
    actuator.updated_at = datetime.now()
    db.commit()

    print(f"📡 Status aktuator update dari MQTT: {device_name} → {'ON' if is_active else 'OFF'}")
    return True


def get_all_status(db: Session) -> list:
    """Ambil status semua aktuator — untuk endpoint GET /actuator-status"""
    return db.query(ActuatorStatus).all()