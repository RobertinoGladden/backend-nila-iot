from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Prediction
from app.schemas import PredictionResponse, PredictRequest, PredictResponse
from app.services.ai_service import predict

router = APIRouter(prefix="/predictions", tags=["Predictions"])


@router.get("/", response_model=List[PredictionResponse], summary="Ambil semua prediksi")
def get_predictions(
    limit:  int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0,  ge=0),
    status: str = Query(default=None, description="Filter: Normal / Waspada / Kritis"),
    db: Session = Depends(get_db)
):
    """
    Ambil hasil prediksi AI.
    Bisa filter berdasarkan status.
    """
    query = db.query(Prediction)

    if status:
        query = query.filter(Prediction.status == status)

    data = (
        query
        .order_by(Prediction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return data


@router.get("/latest", response_model=PredictionResponse, summary="Prediksi terbaru")
def get_latest_prediction(db: Session = Depends(get_db)):
    """Prediksi AI paling baru — endpoint utama polling Flutter"""
    data = (
        db.query(Prediction)
        .order_by(Prediction.created_at.desc())
        .first()
    )
    if not data:
        raise HTTPException(status_code=404, detail="Belum ada prediksi")
    return data


@router.get("/history", response_model=List[PredictionResponse], summary="History prediksi N jam")
def get_prediction_history(
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db)
):
    """History prediksi untuk grafik tren status kualitas air"""
    cutoff = datetime.now() - timedelta(hours=hours)
    data = (
        db.query(Prediction)
        .filter(Prediction.created_at >= cutoff)
        .order_by(Prediction.created_at.asc())
        .all()
    )
    return data


@router.post("/predict", response_model=PredictResponse, summary="Test prediksi manual")
def predict_manual(payload: PredictRequest):
    """
    Test prediksi AI tanpa simpan ke DB.
    Berguna untuk testing model dari Postman atau Flutter.
    """
    result = predict(
        tds         = payload.tds,
        ph          = payload.ph,
        do_level    = payload.do_level,
        temperature = payload.temperature,
        turbidity   = payload.turbidity,
    )
    return PredictResponse(
        status      = result["status"],
        confidence  = result["confidence"],
        urgency     = result["urgency"],
        action      = result["action"],
        probability = {
            "Normal":  result["prob_normal"],
            "Waspada": result["prob_waspada"],
            "Kritis":  result["prob_kritis"],
        }
    )


@router.get("/{prediction_id}", response_model=PredictionResponse, summary="Detail satu prediksi")
def get_prediction_by_id(prediction_id: int, db: Session = Depends(get_db)):
    data = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not data:
        raise HTTPException(status_code=404, detail=f"Prediction id={prediction_id} tidak ditemukan")
    return data