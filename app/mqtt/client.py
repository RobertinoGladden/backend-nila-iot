"""MQTT Client — supports both public broker and authenticated (private/cloud)"""
import os

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

# ── Config ─────────────────────────────────────────────────────
BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "broker.hivemq.com")
BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", 1883))
CLIENT_ID   = os.getenv("MQTT_CLIENT_ID", "nilaiot-backend")
USERNAME    = os.getenv("MQTT_USERNAME", "")
PASSWORD    = os.getenv("MQTT_PASSWORD", "")

# TLS — aktifkan untuk HiveMQ Cloud (port 8883) atau broker production
MQTT_USE_TLS = os.getenv("MQTT_USE_TLS", "false").lower() == "true"

# ── Topics ─────────────────────────────────────────────────────
TOPIC_SENSOR           = os.getenv("MQTT_TOPIC_SENSOR",           "aqua/sensor/data")
TOPIC_ACTUATOR_COMMAND = os.getenv("MQTT_TOPIC_ACTUATOR_COMMAND", "aqua/actuator/command")
TOPIC_ACTUATOR_STATUS  = os.getenv("MQTT_TOPIC_ACTUATOR_STATUS",  "aqua/actuator/status")
TOPIC_ALERT            = os.getenv("MQTT_TOPIC_ALERT",            "aqua/alert")

_mqtt_client: mqtt.Client = None


def get_mqtt_client() -> mqtt.Client:
    return _mqtt_client


def create_mqtt_client(on_message_callback) -> mqtt.Client:
    """
    Buat MQTT client.

    Konfigurasi di .env:
      - Public broker  : MQTT_BROKER_HOST=broker.hivemq.com, port 1883
      - Private broker : set MQTT_USERNAME + MQTT_PASSWORD
      - HiveMQ Cloud   : set MQTT_USE_TLS=true, port 8883
    """
    global _mqtt_client

    client = mqtt.Client(client_id=CLIENT_ID, clean_session=True)

    # Auth — wajib untuk private/cloud broker
    if USERNAME and PASSWORD:
        client.username_pw_set(USERNAME, PASSWORD)
    elif BROKER_HOST != "broker.hivemq.com":
        print("  WRN MQTT_USERNAME/PASSWORD tidak diset untuk non-public broker!")

    # TLS untuk HiveMQ Cloud atau broker production
    if MQTT_USE_TLS:
        import ssl
        client.tls_set(tls_version=ssl.PROTOCOL_TLS)
        print("  OK  MQTT TLS enabled")

    # ── Callbacks ──────────────────────────────────────────────
    def on_connect(client, userdata, flags, rc):
        rc_messages = {
            0: "Connected",
            1: "Wrong protocol version",
            2: "Invalid client ID",
            3: "Server unavailable",
            4: "Bad username/password",
            5: "Not authorized",
        }
        msg = rc_messages.get(rc, f"Unknown rc={rc}")
        if rc == 0:
            print(f"  OK  MQTT {msg} → {BROKER_HOST}:{BROKER_PORT}")
            client.subscribe(TOPIC_SENSOR,          qos=1)
            client.subscribe(TOPIC_ACTUATOR_STATUS, qos=1)
            print(f"  OK  Subscribe: {TOPIC_SENSOR}")
            print(f"  OK  Subscribe: {TOPIC_ACTUATOR_STATUS}")
        else:
            print(f"  ERR MQTT {msg}")

    def on_disconnect(client, userdata, rc):
        if rc != 0:
            print(f"  WRN MQTT Disconnected (rc={rc}) — akan reconnect otomatis")

    def on_subscribe(client, userdata, mid, granted_qos):
        pass  # sudah di-print di on_connect

    def on_publish(client, userdata, mid):
        pass  # silent untuk tidak spam log

    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_subscribe  = on_subscribe
    client.on_publish    = on_publish
    client.on_message    = on_message_callback

    client.reconnect_delay_set(min_delay=1, max_delay=30)

    _mqtt_client = client
    return client


def connect_mqtt(client: mqtt.Client):
    """Connect ke broker dan mulai background loop."""
    print(f"  ...  Connecting MQTT → {BROKER_HOST}:{BROKER_PORT}")
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()


def disconnect_mqtt(client: mqtt.Client):
    """Disconnect bersih saat shutdown."""
    if client:
        client.loop_stop()
        client.disconnect()
        print("MQTT disconnected")
