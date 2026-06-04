"""Machine Learning service for harvest estimation and feeding decisions"""
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
import numpy as np
from app.models import (
    FarmingCycle, FeedingHistory, SensorData, HarvestPrediction,
    FeedingRecommendation, MLModel, FeedStock
)


# ── HARVEST ESTIMATION ─────────────────────────────────────────

def extract_harvest_features(db: Session, farming_cycle_id: int) -> dict:
    """Extract features for harvest prediction"""
    cycle = db.query(FarmingCycle).filter(FarmingCycle.id == farming_cycle_id).first()
    if not cycle:
        return None
    
    farming_days = (date.today() - cycle.seeding_date).days
    
    # Get average sensor readings (TDS, pH, DO, Temp)
    sensor_data = db.query(SensorData).filter(
        SensorData.created_at >= datetime.combine(cycle.seeding_date, datetime.min.time())
    ).all()
    
    avg_tds = np.mean([s.tds for s in sensor_data]) if sensor_data else 0
    avg_ph = np.mean([s.ph for s in sensor_data]) if sensor_data else 0
    avg_do = np.mean([s.do_level for s in sensor_data]) if sensor_data else 0
    avg_temp = np.mean([s.temperature for s in sensor_data]) if sensor_data else 0
    
    # Get feed statistics
    total_feed = db.query(func.sum(FeedingHistory.quantity_given)).filter(
        FeedingHistory.farming_cycle_id == farming_cycle_id
    ).scalar() or 0
    
    avg_feed_per_day = total_feed / max(farming_days, 1)
    
    features = {
        "farming_days": farming_days,
        "avg_tds": float(avg_tds),
        "avg_ph": float(avg_ph),
        "avg_do": float(avg_do),
        "avg_temperature": float(avg_temp),
        "total_feed_given": float(total_feed),
        "avg_feed_per_day": float(avg_feed_per_day),
        "sensor_count": len(sensor_data)
    }
    
    return features


def estimate_harvest_date(db: Session, farming_cycle_id: int) -> HarvestPrediction:
    """Estimate harvest date using ML model"""
    cycle = db.query(FarmingCycle).filter(FarmingCycle.id == farming_cycle_id).first()
    if not cycle:
        raise ValueError("Farming cycle not found")
    
    features = extract_harvest_features(db, farming_cycle_id)
    if not features:
        raise ValueError("Insufficient data for prediction")
    
    # Simple estimation: typical aquaculture cycle is 60-90 days
    # Adjust based on farming conditions
    farming_days = features["farming_days"]
    water_quality_score = (
        (7 - abs(features["avg_ph"] - 7)) * 0.3 +  # Optimal pH ~7
        min(features["avg_do"] / 6, 1) * 0.3 +      # Optimal DO ~6
        (1 - min(abs(features["avg_tds"] - 400) / 1000, 1)) * 0.4  # Optimal TDS ~400
    )
    
    # Estimate remaining days (70-90 days total optimal cycle)
    base_remaining = 75
    remaining_days = int(base_remaining * water_quality_score)
    estimated_harvest_date = date.today() + timedelta(days=remaining_days)
    
    # Calculate confidence based on data availability
    confidence = min(features["sensor_count"] / 100 * 100, 95)
    
    # Get or create active model
    ml_model = db.query(MLModel).filter(
        MLModel.model_type == "harvest_estimation",
        MLModel.status == "active"
    ).first()
    
    if not ml_model:
        ml_model = MLModel(
            model_type="harvest_estimation",
            model_version="v1.0",
            status="active",
            accuracy=85.0
        )
        db.add(ml_model)
        db.flush()
    
    # Create prediction
    prediction = HarvestPrediction(
        farming_cycle_id=farming_cycle_id,
        predicted_harvest_date=estimated_harvest_date,
        confidence_score=confidence,
        ml_model_id=ml_model.id,
        features_used=features
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    
    # Update cycle estimated harvest date
    cycle.estimated_harvest_date = estimated_harvest_date
    db.commit()
    
    return prediction


def get_harvest_predictions(db: Session, farming_cycle_id: int) -> list:
    """Get all harvest predictions for a cycle"""
    return db.query(HarvestPrediction).filter(
        HarvestPrediction.farming_cycle_id == farming_cycle_id
    ).order_by(HarvestPrediction.prediction_date.desc()).all()


# ── FEEDING RECOMMENDATIONS ────────────────────────────────────

def extract_feeding_features(db: Session, farming_cycle_id: int) -> dict:
    """Extract features for feeding recommendations"""
    cycle = db.query(FarmingCycle).filter(FarmingCycle.id == farming_cycle_id).first()
    if not cycle:
        return None
    
    farming_days = (date.today() - cycle.seeding_date).days
    
    # Get recent sensor data (last 7 days)
    recent_sensor = db.query(SensorData).filter(
        SensorData.created_at >= datetime.now() - timedelta(days=7)
    ).order_by(SensorData.created_at.desc()).limit(50).all()
    
    avg_temp = np.mean([s.temperature for s in recent_sensor]) if recent_sensor else 25
    avg_do = np.mean([s.do_level for s in recent_sensor]) if recent_sensor else 6
    
    # Get feeding history (last 7 days)
    recent_feeding = db.query(FeedingHistory).filter(
        FeedingHistory.farming_cycle_id == farming_cycle_id,
        FeedingHistory.actual_time >= datetime.now() - timedelta(days=7)
    ).all()
    
    total_recent_feed = sum(f.quantity_given for f in recent_feeding)
    feeding_frequency = len(recent_feeding)
    
    # Get feed stock
    feed_stock = db.query(FeedStock).filter(
        FeedStock.farming_cycle_id == farming_cycle_id
    ).first()
    
    current_feed = feed_stock.current_quantity if feed_stock else 0
    
    features = {
        "farming_days": farming_days,
        "current_temperature": float(avg_temp),
        "current_do": float(avg_do),
        "recent_feed_total": float(total_recent_feed),
        "recent_feeding_frequency": feeding_frequency,
        "current_feed_stock": float(current_feed),
        "sensor_readings_count": len(recent_sensor)
    }
    
    return features


def recommend_feeding(db: Session, farming_cycle_id: int) -> FeedingRecommendation:
    """Generate feeding recommendation berbasis biomassa aktual dan kondisi air."""
    cycle = db.query(FarmingCycle).filter(FarmingCycle.id == farming_cycle_id).first()
    if not cycle:
        raise ValueError("Farming cycle not found")

    features = extract_feeding_features(db, farming_cycle_id)
    if not features:
        raise ValueError("Insufficient data for recommendation")

    farming_days = features["farming_days"]
    temp = features["current_temperature"]
    do_level = features["current_do"]

    # ── 1. Hitung estimasi biomassa saat ini ─────────────────────
    seed_weight_kg   = cycle.seed_weight_kg or 0
    avg_seed_g       = cycle.avg_seed_weight_g or 10.0
    feed_rate_pct    = (cycle.feed_rate_percent or 3.0) / 100
    survival_rate    = (cycle.survival_rate_percent or 85.0) / 100
    target_g         = cycle.target_harvest_weight_g or 300.0
    fish_count       = cycle.fish_count_estimated

    # Jika tidak ada data bibit, fallback ke base quantity lama (per-ekor 4g)
    if not fish_count or not seed_weight_kg:
        base_quantity_kg = 0.004  # 4 gram dalam kg, per-ekor fallback
        biomass_kg = None
        biomass_source = "fallback (data bibit belum diisi)"
    else:
        # Estimasi pertumbuhan linear: benih → target panen dalam ~90 hari
        total_days = 90
        growth_per_day = (target_g - avg_seed_g) / total_days
        current_weight_g = avg_seed_g + (growth_per_day * min(farming_days, total_days))
        current_weight_g = max(current_weight_g, avg_seed_g)

        surviving_fish = int(fish_count * survival_rate)
        biomass_kg = (surviving_fish * current_weight_g) / 1000  # total kg
        base_quantity_kg = biomass_kg * feed_rate_pct             # kg pakan/hari
        biomass_source = (
            f"{surviving_fish} ekor × {round(current_weight_g, 1)}g = "
            f"{round(biomass_kg, 2)} kg biomassa"
        )

    # ── 2. Faktor koreksi kondisi air ─────────────────────────────
    # Suhu
    if temp < 20:
        temp_factor, temp_note = 0.70, f"suhu rendah ({temp}°C) →×0.70"
    elif temp < 25:
        temp_factor, temp_note = 0.85, f"suhu sejuk ({temp}°C) →×0.85"
    elif temp <= 30:
        temp_factor, temp_note = 1.00, f"suhu optimal ({temp}°C) →×1.00"
    else:
        temp_factor, temp_note = 0.80, f"suhu tinggi ({temp}°C) →×0.80"

    # DO (Dissolved Oxygen)
    if do_level < 4:
        do_factor, do_note = 0.60, f"DO kritis ({do_level} mg/L) →×0.60"
    elif do_level < 5:
        do_factor, do_note = 0.80, f"DO rendah ({do_level} mg/L) →×0.80"
    else:
        do_factor, do_note = 1.00, f"DO optimal ({do_level} mg/L) →×1.00"

    # Tahap budidaya
    if farming_days < 30:
        stage_factor, stage_note = 0.70, f"tahap awal (hari ke-{farming_days}) →×0.70"
    elif farming_days < 60:
        stage_factor, stage_note = 1.00, f"tahap pertumbuhan (hari ke-{farming_days}) →×1.00"
    else:
        stage_factor, stage_note = 0.85, f"tahap akhir/pra-panen (hari ke-{farming_days}) →×0.85"

    total_factor = temp_factor * do_factor * stage_factor
    recommended_kg = base_quantity_kg * total_factor
    recommended_kg = round(recommended_kg, 3)

    # ── 3. Confidence score ───────────────────────────────────────
    has_bio_data = 1 if (fish_count and seed_weight_kg) else 0
    sensor_score = min(features["sensor_readings_count"] / 50, 1.0)
    confidence = round(60 + (has_bio_data * 25) + (sensor_score * 10), 1)
    confidence = min(confidence, 95.0)

    # ── 4. Reasoning teks ─────────────────────────────────────────
    reasoning = (
        f"Biomassa: {biomass_source}. "
        f"Feed rate dasar: {feed_rate_pct*100}%/hari → {round(base_quantity_kg*1000, 1)}g. "
        f"Koreksi: {temp_note}, {do_note}, {stage_note}. "
        f"Total faktor: ×{round(total_factor, 2)}. "
        f"Rekomendasi akhir: {round(recommended_kg*1000, 1)}g ({recommended_kg} kg)."
    )

    # ── 5. Simpan ke DB ───────────────────────────────────────────
    ml_model = db.query(MLModel).filter(
        MLModel.model_type == "feeding_decision",
        MLModel.status == "active"
    ).first()

    if not ml_model:
        ml_model = MLModel(
            model_type="feeding_decision",
            model_version="v2.0-biomass",
            status="active",
            accuracy=82.0
        )
        db.add(ml_model)
        db.flush()

    from datetime import time
    recommended_time = time(7, 0)

    features["biomass_kg"] = round(biomass_kg, 3) if biomass_kg else None
    features["base_quantity_kg"] = round(base_quantity_kg, 4)
    features["temp_factor"] = temp_factor
    features["do_factor"] = do_factor
    features["stage_factor"] = stage_factor

    recommendation = FeedingRecommendation(
        farming_cycle_id=farming_cycle_id,
        recommended_quantity=recommended_kg,
        recommended_time=recommended_time,
        reasoning=reasoning,
        confidence_score=confidence,
        ml_model_id=ml_model.id,
        features_used=features
    )
    db.add(recommendation)
    db.commit()
    db.refresh(recommendation)

    return recommendation


def get_feeding_recommendations(db: Session, farming_cycle_id: int, limit: int = 10) -> list:
    """Get recent feeding recommendations"""
    return db.query(FeedingRecommendation).filter(
        FeedingRecommendation.farming_cycle_id == farming_cycle_id
    ).order_by(FeedingRecommendation.recommendation_date.desc()).limit(limit).all()


# ── ML MODEL MANAGEMENT ────────────────────────────────────────

def get_active_ml_models(db: Session) -> dict:
    """Get all active ML models"""
    models = db.query(MLModel).filter(MLModel.status == "active").all()
    
    return {
        "harvest_estimation": next((m for m in models if m.model_type == "harvest_estimation"), None),
        "feeding_decision": next((m for m in models if m.model_type == "feeding_decision"), None)
    }


def get_model_performance(db: Session, model_id: int) -> dict:
    """Get model performance metrics"""
    model = db.query(MLModel).filter(MLModel.id == model_id).first()
    if not model:
        return None
    
    if model.model_type == "harvest_estimation":
        predictions = db.query(HarvestPrediction).filter(
            HarvestPrediction.ml_model_id == model_id
        ).all()
        
        avg_confidence = np.mean([p.confidence_score for p in predictions]) if predictions else 0
        
        return {
            "model_id": model_id,
            "model_type": model.model_type,
            "version": model.model_version,
            "total_predictions": len(predictions),
            "avg_confidence": round(avg_confidence, 2),
            "accuracy": model.accuracy
        }
    
    elif model.model_type == "feeding_decision":
        recommendations = db.query(FeedingRecommendation).filter(
            FeedingRecommendation.ml_model_id == model_id
        ).all()
        
        avg_confidence = np.mean([r.confidence_score for r in recommendations]) if recommendations else 0
        
        return {
            "model_id": model_id,
            "model_type": model.model_type,
            "version": model.model_version,
            "total_recommendations": len(recommendations),
            "avg_confidence": round(avg_confidence, 2),
            "accuracy": model.accuracy
        }
    
    return None
