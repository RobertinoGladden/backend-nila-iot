"""Feed stock and feeding management service"""
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import FeedStock, FeedTransaction, FeedingSchedule, FeedingHistory
from app.schemas import (
    FeedTransactionCreate, FeedingScheduleCreate, FeedingHistoryCreate,
    FeedStockUpdate, FeedingScheduleUpdate
)


# ── FEED STOCK ─────────────────────────────────────────────────

def get_feed_stock(db: Session, stock_id: int) -> FeedStock:
    return db.query(FeedStock).filter(FeedStock.id == stock_id).first()


def get_user_feed_stocks(db: Session, user_id: int) -> list:
    return db.query(FeedStock).filter(FeedStock.user_id == user_id).all()


def get_farming_cycle_feed_stock(db: Session, farming_cycle_id: int) -> FeedStock:
    return db.query(FeedStock).filter(
        FeedStock.farming_cycle_id == farming_cycle_id
    ).first()


def update_feed_stock(db: Session, stock_id: int, update_data: FeedStockUpdate) -> FeedStock:
    """Update min_threshold atau unit pada feed stock"""
    stock = get_feed_stock(db, stock_id)
    if not stock:
        return None

    if update_data.min_threshold is not None:
        stock.min_threshold = update_data.min_threshold
    if update_data.unit is not None:
        stock.unit = update_data.unit

    stock.updated_at = datetime.now()
    db.commit()
    db.refresh(stock)
    return stock


# ── FEED TRANSACTIONS ──────────────────────────────────────────

def record_feed_transaction(db: Session, stock_id: int, transaction: FeedTransactionCreate) -> FeedTransaction:
    """Record transaksi stok pakan (input atau usage)"""
    feed_stock = get_feed_stock(db, stock_id)
    if not feed_stock:
        raise ValueError("Feed stock not found")

    previous_quantity = feed_stock.current_quantity

    if transaction.transaction_type == "input":
        new_quantity = previous_quantity + transaction.quantity
    elif transaction.transaction_type == "usage":
        if transaction.quantity > previous_quantity:
            raise ValueError(
                f"Stok tidak cukup. Tersedia: {previous_quantity} kg, "
                f"Diminta: {transaction.quantity} kg"
            )
        new_quantity = previous_quantity - transaction.quantity
    else:
        raise ValueError("transaction_type harus 'input' atau 'usage'")

    feed_tx = FeedTransaction(
        feed_stock_id=stock_id,
        transaction_type=transaction.transaction_type,
        quantity=transaction.quantity,
        notes=transaction.notes,
        previous_quantity=previous_quantity,
        new_quantity=new_quantity
    )
    db.add(feed_tx)

    feed_stock.current_quantity = new_quantity
    feed_stock.updated_at = datetime.now()

    db.commit()
    db.refresh(feed_tx)
    return feed_tx


def get_feed_history(db: Session, stock_id: int, limit: int = 100) -> list:
    return db.query(FeedTransaction).filter(
        FeedTransaction.feed_stock_id == stock_id
    ).order_by(FeedTransaction.created_at.desc()).limit(limit).all()


def get_feed_statistics(db: Session, stock_id: int) -> dict:
    stock = get_feed_stock(db, stock_id)
    if not stock:
        return None

    total_input = db.query(func.sum(FeedTransaction.quantity)).filter(
        FeedTransaction.feed_stock_id == stock_id,
        FeedTransaction.transaction_type == "input"
    ).scalar() or 0

    total_usage = db.query(func.sum(FeedTransaction.quantity)).filter(
        FeedTransaction.feed_stock_id == stock_id,
        FeedTransaction.transaction_type == "usage"
    ).scalar() or 0

    tx_count = db.query(FeedTransaction).filter(
        FeedTransaction.feed_stock_id == stock_id
    ).count()

    return {
        "stock_id":         stock_id,
        "current_quantity": stock.current_quantity,
        "unit":             stock.unit,
        "total_input":      total_input,
        "total_usage":      total_usage,
        "transaction_count": tx_count,
        "min_threshold":    stock.min_threshold,
        "below_threshold":  (
            stock.current_quantity < stock.min_threshold
            if stock.min_threshold else False
        )
    }


# ── FEEDING SCHEDULE ───────────────────────────────────────────

def create_feeding_schedule(db: Session, farming_cycle_id: int, schedule_data: FeedingScheduleCreate) -> FeedingSchedule:
    schedule = FeedingSchedule(
        farming_cycle_id=farming_cycle_id,
        scheduled_time=schedule_data.scheduled_time,
        expected_quantity=schedule_data.expected_quantity,
        frequency=schedule_data.frequency,
        status="active"
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


def get_feeding_schedule(db: Session, schedule_id: int) -> FeedingSchedule:
    return db.query(FeedingSchedule).filter(FeedingSchedule.id == schedule_id).first()


def get_farming_cycle_schedules(db: Session, farming_cycle_id: int) -> list:
    return db.query(FeedingSchedule).filter(
        FeedingSchedule.farming_cycle_id == farming_cycle_id
    ).order_by(FeedingSchedule.scheduled_time).all()


def update_feeding_schedule(db: Session, schedule_id: int, update_data: FeedingScheduleUpdate) -> FeedingSchedule:
    """Update jadwal pakan (waktu, kuantitas, frekuensi, status)"""
    schedule = get_feeding_schedule(db, schedule_id)
    if not schedule:
        return None

    if update_data.scheduled_time is not None:
        schedule.scheduled_time = update_data.scheduled_time
    if update_data.expected_quantity is not None:
        schedule.expected_quantity = update_data.expected_quantity
    if update_data.frequency is not None:
        schedule.frequency = update_data.frequency
    if update_data.status is not None:
        if update_data.status not in ["active", "inactive"]:
            raise ValueError("status harus 'active' atau 'inactive'")
        schedule.status = update_data.status

    schedule.updated_at = datetime.now()
    db.commit()
    db.refresh(schedule)
    return schedule


def delete_feeding_schedule(db: Session, schedule_id: int) -> bool:
    schedule = get_feeding_schedule(db, schedule_id)
    if not schedule:
        return False
    db.delete(schedule)
    db.commit()
    return True


# ── FEEDING HISTORY ────────────────────────────────────────────

def record_feeding(db: Session, farming_cycle_id: int, feeding_data: FeedingHistoryCreate) -> FeedingHistory:
    feeding = FeedingHistory(
        feeding_schedule_id=feeding_data.feeding_schedule_id,
        farming_cycle_id=farming_cycle_id,
        actual_time=datetime.now(),
        quantity_given=feeding_data.quantity_given,
        administered_by=feeding_data.administered_by,
        notes=feeding_data.notes
    )
    db.add(feeding)
    db.commit()
    db.refresh(feeding)
    return feeding


def get_feeding_history(db: Session, farming_cycle_id: int, limit: int = 100) -> list:
    return db.query(FeedingHistory).filter(
        FeedingHistory.farming_cycle_id == farming_cycle_id
    ).order_by(FeedingHistory.created_at.desc()).limit(limit).all()


def get_feeding_statistics(db: Session, farming_cycle_id: int) -> dict:
    total_events = db.query(FeedingHistory).filter(
        FeedingHistory.farming_cycle_id == farming_cycle_id
    ).count()

    total_quantity = db.query(func.sum(FeedingHistory.quantity_given)).filter(
        FeedingHistory.farming_cycle_id == farming_cycle_id
    ).scalar() or 0

    avg_quantity = db.query(func.avg(FeedingHistory.quantity_given)).filter(
        FeedingHistory.farming_cycle_id == farming_cycle_id
    ).scalar() or 0

    active_schedules = db.query(FeedingSchedule).filter(
        FeedingSchedule.farming_cycle_id == farming_cycle_id,
        FeedingSchedule.status == "active"
    ).count()

    return {
        "farming_cycle_id":    farming_cycle_id,
        "total_feeding_events": total_events,
        "total_feed_quantity": round(total_quantity, 3),
        "average_per_feeding": round(avg_quantity, 3),
        "active_schedules":    active_schedules
    }