from pydantic import BaseModel, Field, field_validator, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, date, time
from enum import Enum


# ── ENUMS ──────────────────────────────────────────────────────

class FarmingCycleStatus(str, Enum):
    PLANNING   = "planning"
    ACTIVE     = "active"
    HARVESTING = "harvesting"
    COMPLETED  = "completed"


class TransactionType(str, Enum):
    INPUT = "input"
    USAGE = "usage"


# ── USER MANAGEMENT SCHEMAS ────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    full_name: str
    phone_number: Optional[str] = None
    greenhouse_location: Optional[str] = None
    address: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "farmer@example.com",
                "password": "securepass123",
                "full_name": "Budi Santoso",
                "phone_number": "+628123456789",
                "greenhouse_location": "Surabaya",
                "address": "Jl. Merdeka No. 1"
            }
        }
    }


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    phone_number: Optional[str] = None
    greenhouse_location: Optional[str] = None
    address: Optional[str] = None
    profile_photo_url: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    greenhouse_location: Optional[str] = None
    address: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


# ── FARMING CYCLE SCHEMAS ──────────────────────────────────────

class FarmingCycleCreate(BaseModel):
    cycle_name: Optional[str] = None
    seeding_date: date
    seed_weight_kg: Optional[float] = Field(None, gt=0, description="Total berat bibit yang ditebar (kg)")
    avg_seed_weight_g: float = Field(default=10.0, gt=0, description="Rata-rata berat 1 bibit (gram)")
    feed_rate_percent: float = Field(default=3.0, ge=1.0, le=10.0, description="% biomassa per hari")
    target_harvest_weight_g: float = Field(default=300.0, gt=0, description="Target berat panen per ekor (gram)")
    survival_rate_percent: float = Field(default=85.0, ge=10.0, le=100.0, description="Estimasi survival rate (%)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "cycle_name": "Siklus Mei 2026",
                "seeding_date": "2026-05-01",
                "seed_weight_kg": 5.0,
                "avg_seed_weight_g": 10.0,
                "feed_rate_percent": 3.0,
                "target_harvest_weight_g": 300.0,
                "survival_rate_percent": 85.0
            }
        }
    }


class FarmingCycleResponse(BaseModel):
    id: int
    user_id: int
    cycle_name: Optional[str]
    seeding_date: date
    estimated_harvest_date: Optional[date]
    actual_harvest_date: Optional[date]
    status: str
    seed_weight_kg: Optional[float]
    fish_count_estimated: Optional[int]
    avg_seed_weight_g: Optional[float]
    feed_rate_percent: Optional[float]
    target_harvest_weight_g: Optional[float]
    survival_rate_percent: Optional[float]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FarmingCycleUpdate(BaseModel):
    cycle_name: Optional[str] = None
    status: Optional[FarmingCycleStatus] = None
    actual_harvest_date: Optional[date] = None
    seed_weight_kg: Optional[float] = Field(None, gt=0)
    avg_seed_weight_g: Optional[float] = Field(None, gt=0)
    feed_rate_percent: Optional[float] = Field(None, ge=1.0, le=10.0)
    survival_rate_percent: Optional[float] = Field(None, ge=10.0, le=100.0)
    target_harvest_weight_g: Optional[float] = Field(None, gt=0)


# ── FEED MANAGEMENT SCHEMAS ────────────────────────────────────

class FeedStockCreate(BaseModel):
    farming_cycle_id: Optional[int] = None
    current_quantity: float = Field(default=0, ge=0)
    unit: str = "kg"
    min_threshold: Optional[float] = Field(None, ge=0)


class FeedStockUpdate(BaseModel):
    min_threshold: Optional[float] = Field(None, ge=0, description="Batas minimum stok untuk alert")
    unit: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "min_threshold": 10.0,
                "unit": "kg"
            }
        }
    }


class FeedStockResponse(BaseModel):
    id: int
    user_id: int
    farming_cycle_id: Optional[int]
    current_quantity: float
    unit: str
    min_threshold: Optional[float]
    updated_at: datetime

    model_config = {"from_attributes": True}


class FeedTransactionCreate(BaseModel):
    transaction_type: TransactionType
    quantity: float = Field(..., gt=0)
    notes: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "transaction_type": "input",
                "quantity": 50.0,
                "notes": "Beli pakan baru"
            }
        }
    }


class FeedTransactionResponse(BaseModel):
    id: int
    feed_stock_id: int
    transaction_type: str
    quantity: float
    notes: Optional[str]
    previous_quantity: Optional[float]
    new_quantity: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── FEEDING SCHEDULE SCHEMAS ───────────────────────────────────

class FeedingScheduleCreate(BaseModel):
    scheduled_time: time
    expected_quantity: float = Field(..., gt=0)
    frequency: str = "daily"

    model_config = {
        "json_schema_extra": {
            "example": {
                "scheduled_time": "07:00:00",
                "expected_quantity": 2.5,
                "frequency": "daily"
            }
        }
    }


class FeedingScheduleUpdate(BaseModel):
    scheduled_time: Optional[time] = None
    expected_quantity: Optional[float] = Field(None, gt=0)
    frequency: Optional[str] = None
    status: Optional[str] = Field(None, description="active / inactive")

    model_config = {
        "json_schema_extra": {
            "example": {
                "expected_quantity": 3.0,
                "status": "inactive"
            }
        }
    }


class FeedingScheduleResponse(BaseModel):
    id: int
    farming_cycle_id: int
    scheduled_time: time
    expected_quantity: float
    frequency: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedingHistoryCreate(BaseModel):
    feeding_schedule_id: Optional[int] = None
    quantity_given: float = Field(..., gt=0)
    administered_by: str = "system"
    notes: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "quantity_given": 2.5,
                "administered_by": "manual",
                "notes": "Pemberian pakan pagi"
            }
        }
    }


class FeedingHistoryResponse(BaseModel):
    id: int
    feeding_schedule_id: Optional[int]
    farming_cycle_id: int
    actual_time: datetime
    quantity_given: float
    administered_by: str
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── SENSOR SCHEMAS ─────────────────────────────────────────────

class SensorCalibrationCreate(BaseModel):
    farming_cycle_id: Optional[int] = None
    sensor_type: str
    calibration_value: float
    reference_value: float
    notes: Optional[str] = None


class SensorCalibrationResponse(BaseModel):
    id: int
    farming_cycle_id: Optional[int]
    sensor_type: str
    calibration_date: datetime
    calibration_value: float
    reference_value: float
    status: str
    notes: Optional[str]

    model_config = {"from_attributes": True}


# ── ML SCHEMAS ─────────────────────────────────────────────────

class HarvestPredictionResponse(BaseModel):
    id: int
    farming_cycle_id: int
    predicted_harvest_date: date
    confidence_score: Optional[float]
    ml_model_id: Optional[int]
    features_used: Optional[Dict[str, Any]]
    prediction_date: datetime

    model_config = {"from_attributes": True}


class FeedingRecommendationResponse(BaseModel):
    id: int
    farming_cycle_id: int
    recommended_quantity: float
    recommended_time: Optional[time]
    reasoning: Optional[str]
    confidence_score: Optional[float]
    ml_model_id: Optional[int]
    features_used: Optional[Dict[str, Any]]
    recommendation_date: datetime

    model_config = {"from_attributes": True}


# ── SENSOR DATA ───────────────────────────────────────────────

class SensorDataCreate(BaseModel):
    device_id:   str   = Field(default="sensor-01")
    tds:         float = Field(..., ge=0, le=5000)
    ph:          float = Field(..., ge=0, le=14)
    do_level:    float = Field(..., ge=0, le=20)
    temperature: float = Field(..., ge=0, le=50)
    turbidity:   float = Field(default=0, ge=0)

    model_config = {
        "json_schema_extra": {
            "example": {
                "device_id":   "sensor-01",
                "tds":         450.5,
                "ph":          7.8,
                "do_level":    6.5,
                "temperature": 27.5,
                "turbidity":   3.1
            }
        }
    }


class SensorDataResponse(BaseModel):
    id:          int
    device_id:   str
    tds:         float
    ph:          float
    do_level:    float
    temperature: float
    turbidity:   float
    created_at:  datetime

    model_config = {"from_attributes": True}


# ── PREDICTIONS ───────────────────────────────────────────────

class PredictionResponse(BaseModel):
    id:             int
    sensor_data_id: int
    status:         str
    confidence:     float
    prob_normal:    float
    prob_waspada:   float
    prob_kritis:    float
    urgency:        str
    model_version:  str
    created_at:     datetime

    model_config = {"from_attributes": True}


# ── ALERTS ────────────────────────────────────────────────────

class AlertResponse(BaseModel):
    id:             int
    sensor_data_id: int
    prediction_id:  Optional[int]
    level:          str
    message:        str
    action:         Optional[str]
    status:         str
    created_at:     datetime
    resolved_at:    Optional[datetime]

    model_config = {"from_attributes": True}


# ── NOTIFICATIONS ─────────────────────────────────────────────

class NotificationResponse(BaseModel):
    id:         int
    alert_id:   int
    title:      str
    message:    str
    is_read:    bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── ACTUATOR ──────────────────────────────────────────────────

class ActuatorControlRequest(BaseModel):
    device_name:  str = Field(..., description="aerator / heater / pompa")
    action:       str = Field(..., description="on / off")
    triggered_by: str = Field(default="manual")

    @field_validator("device_name")
    @classmethod
    def validate_device(cls, v):
        allowed = ["aerator", "heater", "pompa"]
        if v not in allowed:
            raise ValueError(f"device_name harus salah satu dari: {allowed}")
        return v

    @field_validator("action")
    @classmethod
    def validate_action(cls, v):
        if v not in ["on", "off"]:
            raise ValueError("action harus 'on' atau 'off'")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "device_name":  "aerator",
                "action":       "on",
                "triggered_by": "manual"
            }
        }
    }


class ActuatorStatusResponse(BaseModel):
    id:          int
    device_name: str
    is_active:   bool
    mode:        str
    updated_at:  datetime

    model_config = {"from_attributes": True}


class ActuatorLogResponse(BaseModel):
    id:           int
    device_name:  str
    action:       str
    triggered_by: str
    alert_id:     Optional[int]
    created_at:   datetime

    model_config = {"from_attributes": True}


# ── AI PREDICT ────────────────────────────────────────────────

class PredictRequest(BaseModel):
    tds:         float
    ph:          float
    do_level:    float
    temperature: float
    turbidity:   float = 0.0

    model_config = {
        "json_schema_extra": {
            "example": {
                "tds":         450.5,
                "ph":          7.8,
                "do_level":    6.5,
                "temperature": 27.5,
                "turbidity":   3.1
            }
        }
    }


class PredictResponse(BaseModel):
    status:      str
    confidence:  float
    urgency:     str
    action:      str
    probability: dict


# ── DASHBOARD ─────────────────────────────────────────────────

class DashboardResponse(BaseModel):
    latest_sensor:              Optional[SensorDataResponse]
    latest_prediction:          Optional[PredictionResponse]
    active_alerts_count:        int
    unread_notifications_count: int
    actuator_status:            List[ActuatorStatusResponse]