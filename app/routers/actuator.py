from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import ActuatorStatus, ActuatorLog
from app.schemas import (
    ActuatorControlRequest,
    ActuatorStatusResponse,
    ActuatorLogResponse
)
from app.services.actuator_service import control_actuator

router = APIRouter(prefix="/actuator", tags=["Actuator"])


@router.get("/status", response_model=List[ActuatorStatusResponse], summary="Status semua aktuator")
def get_all_actuator_status(db: Session = Depends(get_db)):
    """
    Ambil status real-time semua aktuator.
    Dipanggil Flutter untuk tampilkan toggle on/off.
    """
    data = db.query(ActuatorStatus).all()
    return data


@router.get("/status/{device_name}", response_model=ActuatorStatusResponse, summary="Status satu aktuator")
def get_actuator_status(device_name: str, db: Session = Depends(get_db)):
    """Ambil status satu aktuator berdasarkan nama device"""
    data = db.query(ActuatorStatus).filter(
        ActuatorStatus.device_name == device_name
    ).first()

    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Device '{device_name}' tidak ditemukan. Pilihan: aerator, heater, pompa"
        )
    return data


@router.post("/control", summary="Kontrol aktuator manual")
def control_actuator_endpoint(
    payload: ActuatorControlRequest,
    db: Session = Depends(get_db)
):
    """
    Kontrol aktuator dari Flutter secara manual.

    Flow:
    1. Validasi device_name & action
    2. Update status di DB
    3. Catat di actuator_logs
    4. Publish MQTT ke hardware

    Body:
    {
        "device_name":  "aerator",
        "action":       "on",
        "triggered_by": "manual"
    }
    """
    result = control_actuator(
        db           = db,
        device_name  = payload.device_name,
        action       = payload.action,
        triggered_by = payload.triggered_by,
    )

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])

    return {
        "message":     f"Aktuator {payload.device_name} berhasil di-{payload.action}",
        "device_name": result["device_name"],
        "action":      result["action"],
        "triggered_by": result["triggered_by"],
        "mqtt_sent":   result["mqtt_sent"],
    }


@router.patch("/mode/{device_name}", summary="Ganti mode aktuator manual/auto")
def set_actuator_mode(
    device_name: str,
    mode: str = Query(..., description="manual / auto"),
    db: Session = Depends(get_db)
):
    """
    Ganti mode aktuator antara manual dan auto.

    - auto   → aktuator bisa di-trigger otomatis oleh AI
    - manual → aktuator hanya bisa dikontrol dari Flutter
    """
    if mode not in ["manual", "auto"]:
        raise HTTPException(status_code=400, detail="Mode harus 'manual' atau 'auto'")

    actuator = db.query(ActuatorStatus).filter(
        ActuatorStatus.device_name == device_name
    ).first()

    if not actuator:
        raise HTTPException(
            status_code=404,
            detail=f"Device '{device_name}' tidak ditemukan"
        )

    actuator.mode = mode
    db.commit()
    db.refresh(actuator)

    return {
        "message":     f"Mode {device_name} berhasil diubah ke '{mode}'",
        "device_name": device_name,
        "mode":        mode,
    }


@router.get("/logs", response_model=List[ActuatorLogResponse], summary="Log history aktuator")
def get_actuator_logs(
    device_name: Optional[str] = Query(default=None, description="Filter by device"),
    limit:       int           = Query(default=50, ge=1, le=500),
    offset:      int           = Query(default=0,  ge=0),
    db: Session = Depends(get_db)
):
    """
    Ambil history log aktuator.
    Bisa filter berdasarkan nama device.
    """
    query = db.query(ActuatorLog)

    if device_name:
        query = query.filter(ActuatorLog.device_name == device_name)

    data = (
        query
        .order_by(ActuatorLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return data


@router.get("/logs/{device_name}", response_model=List[ActuatorLogResponse], summary="Log satu device")
def get_device_logs(
    device_name: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Log history untuk satu device spesifik"""
    data = (
        db.query(ActuatorLog)
        .filter(ActuatorLog.device_name == device_name)
        .order_by(ActuatorLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return data