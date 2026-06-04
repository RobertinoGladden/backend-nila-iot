"""Machine Learning router — harvest estimation & feeding recommendations"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.auth_service import get_current_user
from app.services.farming_service import get_farming_cycle
from app.services.ml_service import (
    estimate_harvest_date, get_harvest_predictions,
    recommend_feeding, get_feeding_recommendations,
    get_active_ml_models, get_model_performance,
)
from app.schemas import HarvestPredictionResponse, FeedingRecommendationResponse

router = APIRouter(prefix="/ml", tags=["Machine Learning"])


def _check_cycle_ownership(db: Session, farming_cycle_id: int, user: User):
    """Pastikan farming cycle milik user yang request."""
    cycle = get_farming_cycle(db, farming_cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Farming cycle tidak ditemukan")
    if cycle.user_id != user.id:
        raise HTTPException(status_code=403, detail="Akses ditolak")
    return cycle


# ── Harvest Estimation ─────────────────────────────────────────

@router.post(
    "/harvest-estimate/{farming_cycle_id}",
    response_model=HarvestPredictionResponse,
    summary="Prediksi tanggal panen",
)
def predict_harvest(
    farming_cycle_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _check_cycle_ownership(db, farming_cycle_id, user)
    try:
        return estimate_harvest_date(db, farming_cycle_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediksi gagal: {e}")


@router.get(
    "/harvest-estimate/{farming_cycle_id}",
    response_model=List[HarvestPredictionResponse],
    summary="Riwayat prediksi panen",
)
def get_harvest_estimates(
    farming_cycle_id: int,
    limit: int = 10,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _check_cycle_ownership(db, farming_cycle_id, user)
    return get_harvest_predictions(db, farming_cycle_id)[:limit]


# ── Feeding Recommendations ────────────────────────────────────

@router.post(
    "/feeding-recommend/{farming_cycle_id}",
    response_model=FeedingRecommendationResponse,
    summary="Rekomendasi pemberian pakan",
)
def recommend_feeding_endpoint(
    farming_cycle_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _check_cycle_ownership(db, farming_cycle_id, user)
    try:
        return recommend_feeding(db, farming_cycle_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rekomendasi gagal: {e}")


@router.get(
    "/feeding-recommend/{farming_cycle_id}",
    response_model=List[FeedingRecommendationResponse],
    summary="Riwayat rekomendasi pakan",
)
def get_feeding_recommendations_endpoint(
    farming_cycle_id: int,
    limit: int = 10,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _check_cycle_ownership(db, farming_cycle_id, user)
    return get_feeding_recommendations(db, farming_cycle_id, limit)


# ── ML Model Management ────────────────────────────────────────

@router.get("/models", summary="Daftar model aktif")
def list_active_models(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    models = get_active_ml_models(db)

    def _serialize(m):
        if not m:
            return None
        return {"id": m.id, "version": m.model_version, "accuracy": m.accuracy}

    return {
        "harvest_estimation_model": _serialize(models["harvest_estimation"]),
        "feeding_decision_model":   _serialize(models["feeding_decision"]),
    }


@router.get("/models/{model_id}/performance", summary="Performa model")
def get_model_perf(
    model_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    perf = get_model_performance(db, model_id)
    if not perf:
        raise HTTPException(status_code=404, detail="Model tidak ditemukan")
    return perf
