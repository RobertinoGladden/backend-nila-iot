import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import check_db_connection
from app.services.ai_service import load_model
from app.mqtt.client import create_mqtt_client, connect_mqtt, disconnect_mqtt
from app.mqtt.subscriber import on_message
from app.routers import (
    sensor_data, predictions, alerts, notifications, actuator,
    auth, farming_cycle, feed, ml, dashboard,
)

_mqtt_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _mqtt_client

    print("\n" + "=" * 55)
    print("  Aquaculture Backend (NILA) Starting...")
    print("=" * 55)

    # 1. Database
    if check_db_connection():
        print("  OK  Database PostgreSQL terhubung")
    else:
        print("  ERR Database tidak bisa diakses!")

    # 2. AI Model (Random Forest .pkl)
    if load_model():
        print("  OK  AI Model (Random Forest) loaded")
    else:
        print("  WRN AI Model tidak ditemukan — pakai rule-based fallback")

    # 3. MQTT
    try:
        _mqtt_client = create_mqtt_client(on_message_callback=on_message)
        connect_mqtt(_mqtt_client)
        print("  OK  MQTT terhubung")
    except Exception as e:
        print(f"  WRN MQTT gagal connect: {e}")
        _mqtt_client = None

    print("=" * 55)
    print(f"  Docs: http://localhost:{os.getenv('APP_PORT', 8000)}/docs")
    print("=" * 55 + "\n")

    yield

    # Shutdown
    print("\nShutting down...")
    if _mqtt_client:
        disconnect_mqtt(_mqtt_client)
    print("Shutdown selesai")


app = FastAPI(
    title="Aquaculture AI Backend — NILA",
    description="Sistem Monitoring Kualitas Air Budidaya Ikan Nila",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────
# Set CORS_ORIGINS di .env untuk production, misal:
# CORS_ORIGINS=https://app.nila.com,https://admin.nila.com
_cors_raw = os.getenv("CORS_ORIGINS", "*")
_cors_origins = [o.strip() for o in _cors_raw.split(",")] if _cors_raw != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────
app.include_router(sensor_data.router)
app.include_router(predictions.router)
app.include_router(alerts.router)
app.include_router(notifications.router)
app.include_router(actuator.router)
app.include_router(auth.router)
app.include_router(farming_cycle.router)
app.include_router(feed.router)
app.include_router(ml.router)
app.include_router(dashboard.router)


@app.get("/", tags=["Root"])
def root():
    return {
        "service": "Aquaculture AI Backend — NILA",
        "version": "2.0.0",
        "status": "running",
        "time": datetime.now().isoformat(),
        "docs": "/docs",
    }
