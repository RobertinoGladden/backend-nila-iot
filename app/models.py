from sqlalchemy import (
    Column, Integer, Float, String,
    Boolean, Text, TIMESTAMP, ForeignKey, func, Date, Time, JSON
)
from sqlalchemy.orm import relationship
from app.database import Base


# ── User Management Models ─────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    phone_number = Column(String(20))
    greenhouse_location = Column(String(255))
    address = Column(Text)
    profile_photo_url = Column(String)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    user_auth = relationship("UserAuth", back_populates="user", uselist=False)
    farming_cycles = relationship("FarmingCycle", back_populates="user")
    feed_stock = relationship("FeedStock", back_populates="user")


class UserAuth(Base):
    __tablename__ = "user_auth"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="user_auth")


# ── Farming Cycle Models ───────────────────────────────────────

class FarmingCycle(Base):
    __tablename__ = "farming_cycles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_name = Column(String(255))
    seeding_date = Column(Date, nullable=False, index=True)
    estimated_harvest_date = Column(Date)
    actual_harvest_date = Column(Date)
    status = Column(String(20), default="active", index=True)

    # Informasi bibit
    seed_weight_kg = Column(Float, nullable=True)           # Total berat bibit yang ditebar (kg)
    fish_count_estimated = Column(Integer, nullable=True)   # Estimasi jumlah ekor (berat/avg berat bibit)
    avg_seed_weight_g = Column(Float, default=10.0)         # Rata-rata berat 1 bibit dalam gram (default 10g)
    feed_rate_percent = Column(Float, default=3.0)          # Feed rate: % dari biomassa per hari (default 3%)
    target_harvest_weight_g = Column(Float, default=300.0)  # Target berat panen per ekor (gram)
    survival_rate_percent = Column(Float, default=85.0)     # Estimasi survival rate (%)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="farming_cycles")
    feed_stock = relationship("FeedStock", back_populates="farming_cycle")
    feeding_schedule = relationship("FeedingSchedule", back_populates="farming_cycle")
    feeding_history = relationship("FeedingHistory", back_populates="farming_cycle")
    harvest_predictions = relationship("HarvestPrediction", back_populates="farming_cycle")
    feeding_recommendations = relationship("FeedingRecommendation", back_populates="farming_cycle")
    sensor_calibrations = relationship("SensorCalibration", back_populates="farming_cycle")


# ── Feed Management Models ─────────────────────────────────────

class FeedStock(Base):
    __tablename__ = "feed_stock"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    farming_cycle_id = Column(Integer, ForeignKey("farming_cycles.id", ondelete="SET NULL"))
    current_quantity = Column(Float, default=0, nullable=False)
    unit = Column(String(50), default="kg")
    min_threshold = Column(Float)
    updated_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User", back_populates="feed_stock")
    farming_cycle = relationship("FarmingCycle", back_populates="feed_stock")
    transactions = relationship("FeedTransaction", back_populates="feed_stock")


class FeedTransaction(Base):
    __tablename__ = "feed_transactions"

    id = Column(Integer, primary_key=True, index=True)
    feed_stock_id = Column(Integer, ForeignKey("feed_stock.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_type = Column(String(20), nullable=False)  # 'input' or 'usage'
    quantity = Column(Float, nullable=False)
    notes = Column(Text)
    previous_quantity = Column(Float)
    new_quantity = Column(Float)
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)

    feed_stock = relationship("FeedStock", back_populates="transactions")


# ── Feeding Schedule Models ────────────────────────────────────

class FeedingSchedule(Base):
    __tablename__ = "feeding_schedule"

    id = Column(Integer, primary_key=True, index=True)
    farming_cycle_id = Column(Integer, ForeignKey("farming_cycles.id", ondelete="CASCADE"), nullable=False, index=True)
    scheduled_time = Column(Time, nullable=False)
    expected_quantity = Column(Float, nullable=False)
    frequency = Column(String(20), default="daily")
    status = Column(String(20), default="active")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    farming_cycle = relationship("FarmingCycle", back_populates="feeding_schedule")
    history = relationship("FeedingHistory", back_populates="feeding_schedule")


class FeedingHistory(Base):
    __tablename__ = "feeding_history"

    id = Column(Integer, primary_key=True, index=True)
    feeding_schedule_id = Column(Integer, ForeignKey("feeding_schedule.id", ondelete="SET NULL"))
    farming_cycle_id = Column(Integer, ForeignKey("farming_cycles.id", ondelete="CASCADE"), nullable=False, index=True)
    actual_time = Column(TIMESTAMP, nullable=False)
    quantity_given = Column(Float, nullable=False)
    administered_by = Column(String(50), default="system")
    notes = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)

    feeding_schedule = relationship("FeedingSchedule", back_populates="history")
    farming_cycle = relationship("FarmingCycle", back_populates="feeding_history")


# ── Sensor Integration Models ──────────────────────────────────

class SensorCalibration(Base):
    __tablename__ = "sensor_calibrations"

    id = Column(Integer, primary_key=True, index=True)
    farming_cycle_id = Column(Integer, ForeignKey("farming_cycles.id", ondelete="SET NULL"))
    sensor_type = Column(String(50), nullable=False)
    calibration_date = Column(TIMESTAMP, server_default=func.now())
    calibration_value = Column(Float)
    reference_value = Column(Float)
    status = Column(String(20), default="valid")
    notes = Column(Text)

    farming_cycle = relationship("FarmingCycle", back_populates="sensor_calibrations")


# ── ML Models ──────────────────────────────────────────────────

class MLModel(Base):
    __tablename__ = "ml_models"

    id = Column(Integer, primary_key=True, index=True)
    model_type = Column(String(50), nullable=False, index=True)  # 'harvest_estimation' or 'feeding_decision'
    model_version = Column(String(50), nullable=False)
    model_path = Column(String(255))
    model_params = Column(JSON)
    training_date = Column(TIMESTAMP, server_default=func.now())
    accuracy = Column(Float)
    status = Column(String(20), default="active")
    created_at = Column(TIMESTAMP, server_default=func.now())

    harvest_predictions = relationship("HarvestPrediction", back_populates="ml_model")
    feeding_recommendations = relationship("FeedingRecommendation", back_populates="ml_model")


class HarvestPrediction(Base):
    __tablename__ = "harvest_predictions"

    id = Column(Integer, primary_key=True, index=True)
    farming_cycle_id = Column(Integer, ForeignKey("farming_cycles.id", ondelete="CASCADE"), nullable=False, index=True)
    predicted_harvest_date = Column(Date, nullable=False)
    confidence_score = Column(Float)
    ml_model_id = Column(Integer, ForeignKey("ml_models.id", ondelete="SET NULL"))
    features_used = Column(JSON)
    prediction_date = Column(TIMESTAMP, server_default=func.now(), index=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    farming_cycle = relationship("FarmingCycle", back_populates="harvest_predictions")
    ml_model = relationship("MLModel", back_populates="harvest_predictions")


class FeedingRecommendation(Base):
    __tablename__ = "feeding_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    farming_cycle_id = Column(Integer, ForeignKey("farming_cycles.id", ondelete="CASCADE"), nullable=False, index=True)
    recommended_quantity = Column(Float, nullable=False)
    recommended_time = Column(Time)
    reasoning = Column(Text)
    confidence_score = Column(Float)
    ml_model_id = Column(Integer, ForeignKey("ml_models.id", ondelete="SET NULL"))
    features_used = Column(JSON)
    recommendation_date = Column(TIMESTAMP, server_default=func.now())
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)

    farming_cycle = relationship("FarmingCycle", back_populates="feeding_recommendations")
    ml_model = relationship("MLModel", back_populates="feeding_recommendations")


# ── Original Sensor Models ─────────────────────────────────────

class SensorData(Base):
    __tablename__ = "sensor_data"

    id          = Column(Integer, primary_key=True, index=True)
    device_id   = Column(String(50), default="sensor-01")
    tds         = Column(Float, nullable=False)
    ph          = Column(Float, nullable=False)
    do_level    = Column(Float, nullable=False)
    temperature = Column(Float, nullable=False)
    turbidity   = Column(Float, default=0)
    created_at  = Column(TIMESTAMP, server_default=func.now())

    predictions = relationship("Prediction", back_populates="sensor_data")
    alerts      = relationship("Alert", back_populates="sensor_data")


class Prediction(Base):
    __tablename__ = "predictions"

    id             = Column(Integer, primary_key=True, index=True)
    sensor_data_id = Column(Integer, ForeignKey("sensor_data.id", ondelete="CASCADE"))
    status         = Column(String(10), nullable=False)
    confidence     = Column(Float, nullable=False)
    prob_normal    = Column(Float, default=0)
    prob_waspada   = Column(Float, default=0)
    prob_kritis    = Column(Float, default=0)
    urgency        = Column(String(10), default="low")
    model_version  = Column(String(20), default="RF-v1")
    created_at     = Column(TIMESTAMP, server_default=func.now())

    sensor_data = relationship("SensorData", back_populates="predictions")
    alerts      = relationship("Alert", back_populates="prediction")


class Alert(Base):
    __tablename__ = "alerts"

    id             = Column(Integer, primary_key=True, index=True)
    sensor_data_id = Column(Integer, ForeignKey("sensor_data.id", ondelete="CASCADE"))
    prediction_id  = Column(Integer, ForeignKey("predictions.id", ondelete="SET NULL"), nullable=True)
    level          = Column(String(10), nullable=False)
    message        = Column(Text, nullable=False)
    action         = Column(Text, nullable=True)
    status         = Column(String(10), default="active")
    created_at     = Column(TIMESTAMP, server_default=func.now())
    resolved_at    = Column(TIMESTAMP, nullable=True)

    sensor_data   = relationship("SensorData", back_populates="alerts")
    prediction    = relationship("Prediction", back_populates="alerts")
    notifications = relationship("Notification", back_populates="alert")
    actuator_logs = relationship("ActuatorLog", back_populates="alert")


class Notification(Base):
    __tablename__ = "notifications"

    id         = Column(Integer, primary_key=True, index=True)
    alert_id   = Column(Integer, ForeignKey("alerts.id", ondelete="CASCADE"))
    title      = Column(String(100), nullable=False)
    message    = Column(Text, nullable=False)
    is_read    = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    alert = relationship("Alert", back_populates="notifications")


class ActuatorStatus(Base):
    __tablename__ = "actuator_status"

    id          = Column(Integer, primary_key=True, index=True)
    device_name = Column(String(50), unique=True, nullable=False)
    is_active   = Column(Boolean, default=False)
    mode        = Column(String(10), default="auto")
    updated_at  = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class ActuatorLog(Base):
    __tablename__ = "actuator_logs"

    id           = Column(Integer, primary_key=True, index=True)
    device_name  = Column(String(50), nullable=False)
    action       = Column(String(10), nullable=False)
    triggered_by = Column(String(20), default="manual")
    alert_id     = Column(Integer, ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True)
    created_at   = Column(TIMESTAMP, server_default=func.now())

    alert = relationship("Alert", back_populates="actuator_logs")