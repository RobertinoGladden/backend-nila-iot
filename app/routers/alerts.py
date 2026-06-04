from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Alert
from app.schemas import AlertResponse

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("/", response_model=List[AlertResponse], summary="Ambil semua alert")
def get_alerts(
    status: Optional[str] = Query(default="active", description="active / resolved / all"),
    limit:  int           = Query(default=50, ge=1, le=500),
    offset: int           = Query(default=0,  ge=0),
    db: Session = Depends(get_db)
):
    """
    Ambil daftar alert.
    Default hanya tampilkan yang masih active.
    Gunakan status=all untuk semua.
    """
    query = db.query(Alert)

    if status and status != "all":
        query = query.filter(Alert.status == status)

    data = (
        query
        .order_by(Alert.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return data


@router.get("/active", response_model=List[AlertResponse], summary="Alert yang masih aktif")
def get_active_alerts(db: Session = Depends(get_db)):
    """Shortcut untuk ambil semua alert aktif — untuk badge di Flutter"""
    data = (
        db.query(Alert)
        .filter(Alert.status == "active")
        .order_by(Alert.created_at.desc())
        .all()
    )
    return data


@router.get("/history", response_model=List[AlertResponse], summary="History alert N jam")
def get_alert_history(
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db)
):
    """History alert N jam terakhir"""
    cutoff = datetime.now() - timedelta(hours=hours)
    data = (
        db.query(Alert)
        .filter(Alert.created_at >= cutoff)
        .order_by(Alert.created_at.asc())
        .all()
    )
    return data


@router.patch("/{alert_id}/resolve", response_model=AlertResponse, summary="Resolve alert")
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    """
    Tandai alert sebagai resolved.
    Dipanggil dari Flutter saat user konfirmasi sudah ditangani.
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert id={alert_id} tidak ditemukan")

    if alert.status == "resolved":
        raise HTTPException(status_code=400, detail="Alert sudah resolved")

    alert.status      = "resolved"
    alert.resolved_at = datetime.now()
    db.commit()
    db.refresh(alert)

    return alert


@router.patch("/resolve-all", summary="Resolve semua alert aktif")
def resolve_all_alerts(db: Session = Depends(get_db)):
    """Resolve semua alert aktif sekaligus"""
    now = datetime.now()
    updated = (
        db.query(Alert)
        .filter(Alert.status == "active")
        .all()
    )
    count = len(updated)
    for alert in updated:
        alert.status      = "resolved"
        alert.resolved_at = now

    db.commit()
    return {"message": f"{count} alert berhasil di-resolve"}


@router.get("/{alert_id}", response_model=AlertResponse, summary="Detail satu alert")
def get_alert_by_id(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert id={alert_id} tidak ditemukan")
    return alert