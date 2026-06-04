"""Feed management router"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import User
from app.services.auth_service import get_current_user
from app.services.feed_service import (
    get_feed_stock, get_user_feed_stocks, get_farming_cycle_feed_stock,
    record_feed_transaction, get_feed_history, get_feed_statistics,
    update_feed_stock,
    create_feeding_schedule, get_farming_cycle_schedules,
    get_feeding_schedule, update_feeding_schedule, delete_feeding_schedule,
    record_feeding, get_feeding_history, get_feeding_statistics,
)
from app.schemas import (
    FeedStockResponse, FeedStockUpdate,
    FeedTransactionCreate, FeedTransactionResponse,
    FeedingScheduleCreate, FeedingScheduleUpdate, FeedingScheduleResponse,
    FeedingHistoryCreate, FeedingHistoryResponse,
)

router = APIRouter(prefix="/feed", tags=["Feed Management"])


# ── HELPERS ────────────────────────────────────────────────────

def _get_cycle(db, farming_cycle_id, user):
    from app.services.farming_service import get_farming_cycle
    cycle = get_farming_cycle(db, farming_cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Farming cycle tidak ditemukan")
    if cycle.user_id != user.id:
        raise HTTPException(status_code=403, detail="Akses ditolak")
    return cycle

def _get_stock(db, stock_id, user):
    stock = get_feed_stock(db, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Feed stock tidak ditemukan")
    if stock.user_id != user.id:
        raise HTTPException(status_code=403, detail="Akses ditolak")
    return stock

def _get_schedule_owned(db, schedule_id, user):
    schedule = get_feeding_schedule(db, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
    # verifikasi kepemilikan via farming cycle
    from app.services.farming_service import get_farming_cycle
    cycle = get_farming_cycle(db, schedule.farming_cycle_id)
    if not cycle or cycle.user_id != user.id:
        raise HTTPException(status_code=403, detail="Akses ditolak")
    return schedule


# ── FEED STOCK ─────────────────────────────────────────────────

@router.get("/stocks", response_model=List[FeedStockResponse], summary="Semua feed stock milik user")
def list_feed_stocks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_user_feed_stocks(db, user.id)


@router.get("/stocks/{farming_cycle_id}", response_model=Optional[FeedStockResponse], summary="Feed stock per siklus")
def get_stock_for_cycle(
    farming_cycle_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _get_cycle(db, farming_cycle_id, user)
    stock = get_farming_cycle_feed_stock(db, farming_cycle_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Feed stock tidak ditemukan")
    return stock


@router.patch("/stocks/{stock_id}", response_model=FeedStockResponse, summary="Update min threshold / unit stok")
def update_stock(
    stock_id: int,
    update_data: FeedStockUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update konfigurasi feed stock.
    - `min_threshold`: batas minimum stok; akan trigger alert jika di bawah ini
    - `unit`: satuan stok (default: kg)
    """
    _get_stock(db, stock_id, user)
    updated = update_feed_stock(db, stock_id, update_data)
    return updated


# ── FEED TRANSACTIONS ──────────────────────────────────────────

@router.post("/stocks/{stock_id}/transaction", response_model=FeedTransactionResponse, summary="Catat transaksi stok pakan")
def record_transaction(
    stock_id: int,
    transaction: FeedTransactionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Catat transaksi stok pakan.
    - `input`: tambah stok (beli pakan)
    - `usage`: kurangi stok (pakan terpakai)
    """
    _get_stock(db, stock_id, user)
    try:
        return record_feed_transaction(db, stock_id, transaction)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transaksi gagal: {e}")


@router.get("/stocks/{stock_id}/history", response_model=List[FeedTransactionResponse], summary="Riwayat transaksi stok")
def get_stock_history(
    stock_id: int,
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _get_stock(db, stock_id, user)
    return get_feed_history(db, stock_id, limit)


@router.get("/stocks/{stock_id}/stats", response_model=dict, summary="Statistik stok pakan")
def get_stock_stats(
    stock_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _get_stock(db, stock_id, user)
    return get_feed_statistics(db, stock_id)


# ── FEEDING SCHEDULE ───────────────────────────────────────────

@router.post("/schedule/{farming_cycle_id}", response_model=FeedingScheduleResponse, summary="Buat jadwal pakan")
def create_schedule(
    farming_cycle_id: int,
    schedule_data: FeedingScheduleCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _get_cycle(db, farming_cycle_id, user)
    try:
        return create_feeding_schedule(db, farming_cycle_id, schedule_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal membuat jadwal: {e}")


@router.get("/schedule/{farming_cycle_id}", response_model=List[FeedingScheduleResponse], summary="Daftar jadwal pakan")
def list_schedules(
    farming_cycle_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _get_cycle(db, farming_cycle_id, user)
    return get_farming_cycle_schedules(db, farming_cycle_id)


@router.patch("/schedule/{schedule_id}", response_model=FeedingScheduleResponse, summary="Update jadwal pakan")
def update_schedule(
    schedule_id: int,
    update_data: FeedingScheduleUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update jadwal pakan.
    - Ubah waktu, kuantitas, atau frekuensi
    - Set `status: inactive` untuk nonaktifkan tanpa menghapus
    """
    _get_schedule_owned(db, schedule_id, user)
    try:
        updated = update_feeding_schedule(db, schedule_id, update_data)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal update jadwal: {e}")


@router.delete("/schedule/{schedule_id}", summary="Hapus jadwal pakan")
def remove_schedule(
    schedule_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _get_schedule_owned(db, schedule_id, user)
    success = delete_feeding_schedule(db, schedule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
    return {"message": f"Jadwal id={schedule_id} berhasil dihapus"}


# ── FEEDING HISTORY ────────────────────────────────────────────

@router.post("/history/{farming_cycle_id}", response_model=FeedingHistoryResponse, summary="Catat pemberian pakan")
def record_feeding_event(
    farming_cycle_id: int,
    feeding_data: FeedingHistoryCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _get_cycle(db, farming_cycle_id, user)
    try:
        return record_feeding(db, farming_cycle_id, feeding_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mencatat pemberian pakan: {e}")


@router.get("/history/{farming_cycle_id}", response_model=List[FeedingHistoryResponse], summary="Riwayat pemberian pakan")
def list_feeding_history(
    farming_cycle_id: int,
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _get_cycle(db, farming_cycle_id, user)
    return get_feeding_history(db, farming_cycle_id, limit)


@router.get("/history/{farming_cycle_id}/stats", response_model=dict, summary="Statistik pemberian pakan")
def get_history_stats(
    farming_cycle_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _get_cycle(db, farming_cycle_id, user)
    return get_feeding_statistics(db, farming_cycle_id)