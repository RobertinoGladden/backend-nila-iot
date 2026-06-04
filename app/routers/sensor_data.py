from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models import SensorData
from app.schemas import SensorDataCreate, SensorDataResponse
from app.services.ai_service import predict
from app.services.alert_service import process_and_save
from app.services.actuator_service import trigger_by_ai
from app.mqtt.publisher import publish_alert

router = APIRouter(prefix="/sensor-data", tags=["Sensor Data"])


@router.post("/", response_model=SensorDataResponse, summary="Kirim data sensor manual")
def create_sensor_data(payload: SensorDataCreate, db: Session = Depends(get_db)):
    """
    Endpoint untuk kirim data sensor secara manual via HTTP POST.
    Bisa dipakai untuk:
    - Testing dari Postman
    - Fallback jika MQTT tidak tersedia
    - Input manual dari Flutter

    Alur sama persis dengan data dari MQTT:
    sensor → AI → prediction → alert → notification → actuator
    """

    # ── 1. Simpan sensor data ─────────────────────────────────
    sensor = SensorData(
        device_id   = payload.device_id,
        tds         = payload.tds,
        ph          = payload.ph,
        do_level    = payload.do_level,
        temperature = payload.temperature,
        turbidity   = payload.turbidity,
    )
    db.add(sensor)
    db.flush()

    # ── 2. Prediksi AI ────────────────────────────────────────
    pred_result = predict(
        tds         = payload.tds,
        ph          = payload.ph,
        do_level    = payload.do_level,
        temperature = payload.temperature,
        turbidity   = payload.turbidity,
    )

    # ── 3. Simpan prediction + alert + notification ───────────
    result = process_and_save(
        db          = db,
        sensor      = sensor,
        pred_result = pred_result,
    )

    # ── 4. Trigger aktuator jika perlu ───────────────────────
    if result["alert"] is not None:
        trigger_by_ai(
            db       = db,
            status   = pred_result["status"],
            alert_id = result["alert"].id,
        )
        publish_alert(
            status     = pred_result["status"],
            urgency    = pred_result["urgency"],
            action     = pred_result["action"],
            confidence = pred_result["confidence"],
        )

    return sensor


@router.get("/", response_model=List[SensorDataResponse], summary="Ambil semua data sensor")
def get_sensor_data(
    limit:  int = Query(default=50,  ge=1, le=500),
    offset: int = Query(default=0,   ge=0),
    db: Session = Depends(get_db)
):
    """
    Ambil data sensor terbaru.
    Gunakan limit & offset untuk pagination.
    """
    data = (
        db.query(SensorData)
        .order_by(SensorData.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return data


@router.get("/latest", response_model=SensorDataResponse, summary="Data sensor terbaru")
def get_latest_sensor(db: Session = Depends(get_db)):
    """Ambil satu data sensor paling baru — untuk polling Flutter"""
    data = (
        db.query(SensorData)
        .order_by(SensorData.created_at.desc())
        .first()
    )
    if not data:
        raise HTTPException(status_code=404, detail="Belum ada data sensor")
    return data


@router.get("/history", response_model=List[SensorDataResponse], summary="History sensor N jam terakhir")
def get_sensor_history(
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db)
):
    """
    Ambil data sensor N jam terakhir.
    Default 24 jam. Maksimal 168 jam (7 hari).
    Cocok untuk grafik tren di Flutter.
    """
    cutoff = datetime.now() - timedelta(hours=hours)
    data = (
        db.query(SensorData)
        .filter(SensorData.created_at >= cutoff)
        .order_by(SensorData.created_at.asc())
        .all()
    )
    return data


@router.get("/{sensor_id}", response_model=SensorDataResponse, summary="Detail satu data sensor")
def get_sensor_by_id(sensor_id: int, db: Session = Depends(get_db)):
    data = db.query(SensorData).filter(SensorData.id == sensor_id).first()
    if not data:
        raise HTTPException(status_code=404, detail=f"Sensor data id={sensor_id} tidak ditemukan")
    return data