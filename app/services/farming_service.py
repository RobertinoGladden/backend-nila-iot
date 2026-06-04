"""Farming cycle management service"""
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import FarmingCycle, FeedStock, FeedingHistory, FeedingSchedule
from app.schemas import FarmingCycleCreate, FarmingCycleUpdate


def create_farming_cycle(db: Session, user_id: int, cycle_data: FarmingCycleCreate) -> FarmingCycle:
    cycle_name = cycle_data.cycle_name or f"Siklus {datetime.now().strftime('%d %b %Y')}"

    # Hitung estimasi jumlah ekor dari total berat bibit
    fish_count_estimated = None
    if cycle_data.seed_weight_kg and cycle_data.avg_seed_weight_g:
        fish_count_estimated = int(
            (cycle_data.seed_weight_kg * 1000) / cycle_data.avg_seed_weight_g
        )

    farming_cycle = FarmingCycle(
        user_id=user_id,
        cycle_name=cycle_name,
        seeding_date=cycle_data.seeding_date,
        status="active",
        seed_weight_kg=cycle_data.seed_weight_kg,
        fish_count_estimated=fish_count_estimated,
        avg_seed_weight_g=cycle_data.avg_seed_weight_g,
        feed_rate_percent=cycle_data.feed_rate_percent,
        target_harvest_weight_g=cycle_data.target_harvest_weight_g,
        survival_rate_percent=cycle_data.survival_rate_percent,
    )
    db.add(farming_cycle)
    db.flush()

    # Auto-create feed stock untuk siklus ini
    feed_stock = FeedStock(
        user_id=user_id,
        farming_cycle_id=farming_cycle.id,
        current_quantity=0,
        unit="kg"
    )
    db.add(feed_stock)
    db.commit()
    db.refresh(farming_cycle)
    return farming_cycle


def get_farming_cycle(db: Session, cycle_id: int) -> FarmingCycle:
    return db.query(FarmingCycle).filter(FarmingCycle.id == cycle_id).first()


def get_user_farming_cycles(db: Session, user_id: int) -> list:
    return db.query(FarmingCycle).filter(
        FarmingCycle.user_id == user_id
    ).order_by(FarmingCycle.created_at.desc()).all()


def get_active_farming_cycle(db: Session, user_id: int) -> FarmingCycle:
    return db.query(FarmingCycle).filter(
        FarmingCycle.user_id == user_id,
        FarmingCycle.status == "active"
    ).first()


def calculate_farming_days(seeding_date: date) -> int:
    return (date.today() - seeding_date).days


def update_farming_cycle(db: Session, cycle_id: int, update_data: FarmingCycleUpdate) -> FarmingCycle:
    cycle = get_farming_cycle(db, cycle_id)
    if not cycle:
        return None

    if update_data.cycle_name is not None:
        cycle.cycle_name = update_data.cycle_name
    if update_data.status is not None:
        cycle.status = update_data.status
    if update_data.actual_harvest_date is not None:
        cycle.actual_harvest_date = update_data.actual_harvest_date
        if cycle.status != "completed":
            cycle.status = "completed"
    if update_data.seed_weight_kg is not None:
        cycle.seed_weight_kg = update_data.seed_weight_kg
        # Recalculate fish count jika seed weight diupdate
        if cycle.avg_seed_weight_g:
            cycle.fish_count_estimated = int(
                (update_data.seed_weight_kg * 1000) / cycle.avg_seed_weight_g
            )
    if update_data.avg_seed_weight_g is not None:
        cycle.avg_seed_weight_g = update_data.avg_seed_weight_g
    if update_data.feed_rate_percent is not None:
        cycle.feed_rate_percent = update_data.feed_rate_percent
    if update_data.survival_rate_percent is not None:
        cycle.survival_rate_percent = update_data.survival_rate_percent
    if update_data.target_harvest_weight_g is not None:
        cycle.target_harvest_weight_g = update_data.target_harvest_weight_g

    cycle.updated_at = datetime.now()
    db.commit()
    db.refresh(cycle)
    return cycle


def get_farming_cycle_stats(db: Session, cycle_id: int) -> dict:
    cycle = get_farming_cycle(db, cycle_id)
    if not cycle:
        return None

    farming_days = calculate_farming_days(cycle.seeding_date)

    total_feed_events = db.query(FeedingHistory).filter(
        FeedingHistory.farming_cycle_id == cycle_id
    ).count()

    total_feed_quantity = db.query(func.sum(FeedingHistory.quantity_given)).filter(
        FeedingHistory.farming_cycle_id == cycle_id
    ).scalar() or 0

    schedule_count = db.query(FeedingSchedule).filter(
        FeedingSchedule.farming_cycle_id == cycle_id
    ).count()

    # Estimasi biomassa saat ini — linear growth benih → target panen
    current_biomass_kg = None
    if cycle.fish_count_estimated and cycle.avg_seed_weight_g:
        target_g    = cycle.target_harvest_weight_g or 300.0
        avg_seed_g  = cycle.avg_seed_weight_g or 10.0
        survival    = (cycle.survival_rate_percent or 85.0) / 100
        total_days  = 90
        growth_per_day   = (target_g - avg_seed_g) / total_days
        current_weight_g = avg_seed_g + (growth_per_day * min(farming_days, total_days))
        current_weight_g = max(current_weight_g, avg_seed_g)
        surviving_fish   = int(cycle.fish_count_estimated * survival)
        current_biomass_kg = round((surviving_fish * current_weight_g) / 1000, 2)

    return {
        "cycle_id":            cycle_id,
        "cycle_name":          cycle.cycle_name,
        "status":              cycle.status,
        "seeding_date":        cycle.seeding_date,
        "farming_days":        farming_days,
        "seed_weight_kg":      cycle.seed_weight_kg,
        "fish_count_estimated": cycle.fish_count_estimated,
        "avg_seed_weight_g":   cycle.avg_seed_weight_g,
        "feed_rate_percent":   cycle.feed_rate_percent,
        "survival_rate_percent": cycle.survival_rate_percent,
        "current_biomass_kg":  current_biomass_kg,
        "total_feeding_events": total_feed_events,
        "total_feed_quantity": round(total_feed_quantity, 3),
        "feeding_schedules":   schedule_count,
    }

def delete_farming_cycle(db: Session, cycle_id: int) -> bool:
    """
    Hapus farming cycle beserta data turunannya.

    Membersihkan data anak secara eksplisit agar konsisten di semua backend
    (tidak hanya bergantung pada ON DELETE CASCADE di level database):
    - FeedingHistory   (riwayat pakan)
    - FeedingSchedule  (jadwal pakan)
    - FeedStock + transaksinya
    """
    cycle = get_farming_cycle(db, cycle_id)
    if not cycle:
        return False

    # Hapus riwayat & jadwal pakan milik cycle ini
    db.query(FeedingHistory).filter(
        FeedingHistory.farming_cycle_id == cycle_id
    ).delete(synchronize_session=False)

    db.query(FeedingSchedule).filter(
        FeedingSchedule.farming_cycle_id == cycle_id
    ).delete(synchronize_session=False)

    # Hapus feed stock yang terkait (transaksinya ikut CASCADE via FK)
    stocks = db.query(FeedStock).filter(
        FeedStock.farming_cycle_id == cycle_id
    ).all()
    for stock in stocks:
        db.delete(stock)

    db.delete(cycle)
    db.commit()
    return True
