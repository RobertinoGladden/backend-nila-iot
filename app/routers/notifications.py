from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Notification
from app.schemas import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", response_model=List[NotificationResponse], summary="Ambil semua notifikasi")
def get_notifications(
    is_read: bool = Query(default=None, description="Filter: true=sudah dibaca, false=belum"),
    limit:   int  = Query(default=50, ge=1, le=500),
    offset:  int  = Query(default=0,  ge=0),
    db: Session = Depends(get_db)
):
    """Ambil daftar notifikasi. Bisa filter yang belum dibaca."""
    query = db.query(Notification)

    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)

    data = (
        query
        .order_by(Notification.created_at.desc())
        .offset(offset)
                .limit(limit)
        .all()
    )
    return data


@router.get("/unread", response_model=List[NotificationResponse], summary="Notifikasi belum dibaca")
def get_unread_notifications(db: Session = Depends(get_db)):
    """
    Ambil semua notifikasi yang belum dibaca.
    Untuk badge counter di Flutter.
    """
    data = (
        db.query(Notification)
        .filter(Notification.is_read == False)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return data


@router.get("/unread/count", summary="Jumlah notifikasi belum dibaca")
def get_unread_count(db: Session = Depends(get_db)):
    """Return jumlah notifikasi belum dibaca — untuk badge angka di Flutter"""
    count = (
        db.query(Notification)
        .filter(Notification.is_read == False)
        .count()
    )
    return {"unread_count": count}


@router.patch("/{notif_id}/read", response_model=NotificationResponse, summary="Tandai sudah dibaca")
def mark_as_read(notif_id: int, db: Session = Depends(get_db)):
    """Tandai satu notifikasi sebagai sudah dibaca"""
    notif = db.query(Notification).filter(Notification.id == notif_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail=f"Notification id={notif_id} tidak ditemukan")

    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif


@router.patch("/read-all", summary="Tandai semua notifikasi sudah dibaca")
def mark_all_as_read(db: Session = Depends(get_db)):
    """Tandai semua notifikasi sebagai sudah dibaca sekaligus"""
    notifications = (
        db.query(Notification)
        .filter(Notification.is_read == False)
        .all()
    )
    count = len(notifications)
    for notif in notifications:
        notif.is_read = True

    db.commit()
    return {"message": f"{count} notifikasi ditandai sudah dibaca"}


@router.get("/{notif_id}", response_model=NotificationResponse, summary="Detail satu notifikasi")
def get_notification_by_id(notif_id: int, db: Session = Depends(get_db)):
    notif = db.query(Notification).filter(Notification.id == notif_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail=f"Notification id={notif_id} tidak ditemukan")
    return notif


@router.delete("/{notif_id}", summary="Hapus satu notifikasi")
def delete_notification(notif_id: int, db: Session = Depends(get_db)):
    notif = db.query(Notification).filter(Notification.id == notif_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail=f"Notification id={notif_id} tidak ditemukan")

    db.delete(notif)
    db.commit()
    return {"message": f"Notification id={notif_id} berhasil dihapus"}