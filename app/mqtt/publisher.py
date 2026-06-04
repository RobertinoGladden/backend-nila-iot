import json
import paho.mqtt.client as mqtt
from app.mqtt.client import get_mqtt_client, TOPIC_ACTUATOR_COMMAND, TOPIC_ALERT


def publish_actuator_command(
    device_name: str,
    action: str,
    triggered_by: str = "manual"
) -> bool:
    """
    Publish perintah ke aktuator hardware via MQTT.

    Topic  : aqua/actuator/command
    Payload: {"device": "aerator", "action": "on", "triggered_by": "ai"}

    Dipanggil dari actuator_service.py
    """
    client = get_mqtt_client()
    if not client:
        print("❌ MQTT client belum siap")
        return False

    payload = json.dumps({
        "device":       device_name,
        "action":       action,
        "triggered_by": triggered_by,
    })

    result = client.publish(
        topic   = TOPIC_ACTUATOR_COMMAND,
        payload = payload,
        qos     = 1,  # at least once
    )

    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        print(f"📤 MQTT publish actuator: {device_name} → {action}")
        return True
    else:
        print(f"❌ MQTT publish gagal: rc={result.rc}")
        return False


def publish_alert(
    status: str,
    urgency: str,
    action: str,
    confidence: float
) -> bool:
    """
    Publish alert ke topic MQTT.
    Bisa dipakai Node-RED atau device lain untuk subscribe alert.

    Topic  : aqua/alert
    Payload: {"status": "Kritis", "urgency": "high", ...}
    """
    client = get_mqtt_client()
    if not client:
        return False

    payload = json.dumps({
        "status":     status,
        "urgency":    urgency,
        "action":     action,
        "confidence": confidence,
    })

    result = client.publish(
        topic   = TOPIC_ALERT,
        payload = payload,
        qos     = 1,
    )

    return result.rc == mqtt.MQTT_ERR_SUCCESS