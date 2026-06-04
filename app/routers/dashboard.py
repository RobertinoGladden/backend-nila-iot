"""Dashboard & Summary router"""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SensorData, Prediction, Alert, Notification, ActuatorStatus
from app.schemas import DashboardResponse

router = APIRouter(tags=["Dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)):
    """Ringkasan kondisi terkini: sensor, prediksi, alert, aktuator."""
    latest_sensor = (
        db.query(SensorData).order_by(SensorData.created_at.desc()).first()
    )
    latest_prediction = (
        db.query(Prediction).order_by(Prediction.created_at.desc()).first()
    )
    active_alerts_count = (
        db.query(Alert).filter(Alert.status == "active").count()
    )
    unread_notif_count = (
        db.query(Notification).filter(Notification.is_read == False).count()
    )
    actuator_status = db.query(ActuatorStatus).all()

    return DashboardResponse(
        latest_sensor=latest_sensor,
        latest_prediction=latest_prediction,
        active_alerts_count=active_alerts_count,
        unread_notifications_count=unread_notif_count,
        actuator_status=actuator_status,
    )


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    """Statistik keseluruhan sistem."""
    total_sensor      = db.query(SensorData).count()
    total_predictions = db.query(Prediction).count()
    total_alerts      = db.query(Alert).count()
    active_alerts     = db.query(Alert).filter(Alert.status == "active").count()
    total_notif       = db.query(Notification).count()
    unread_notif      = db.query(Notification).filter(Notification.is_read == False).count()

    status_dist = (
        db.query(Prediction.status, func.count(Prediction.id))
        .group_by(Prediction.status)
        .all()
    )

    actuators = db.query(ActuatorStatus).all()

    return {
        "total_sensor_readings":   total_sensor,
        "total_predictions":       total_predictions,
        "total_alerts":            total_alerts,
        "active_alerts":           active_alerts,
        "total_notifications":     total_notif,
        "unread_notifications":    unread_notif,
        "prediction_distribution": {row[0]: row[1] for row in status_dist},
        "actuators": [
            {"device": a.device_name, "is_active": a.is_active, "mode": a.mode}
            for a in actuators
        ],
        "generated_at": datetime.now().isoformat(),
    }
