"""Authentication router"""
import os
import shutil
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.auth_service import (
    register_user, login_user, get_current_user
)
from app.schemas import UserRegister, UserLogin, UserResponse, UserUpdate, TokenResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, summary="Daftar user baru")
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register user baru dan langsung return token."""
    try:
        user = register_user(db, user_data)
        return login_user(db, UserLogin(email=user_data.email, password=user_data.password))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registrasi gagal: {e}")


@router.post("/login", response_model=TokenResponse, summary="Login")
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """Login dengan email dan password."""
    try:
        return login_user(db, login_data)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login gagal: {e}")


@router.get("/me", response_model=UserResponse, summary="Profil saya")
def get_profile(user: User = Depends(get_current_user)):
    """Ambil profil user yang sedang login."""
    return user


@router.put("/me", response_model=UserResponse, summary="Update profil")
def update_profile(
    update_data: UserUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update profil user yang sedang login."""
    if update_data.full_name is not None:
        user.full_name = update_data.full_name
    if update_data.phone_number is not None:
        user.phone_number = update_data.phone_number
    if update_data.greenhouse_location is not None:
        user.greenhouse_location = update_data.greenhouse_location
    if update_data.address is not None:
        user.address = update_data.address

    from datetime import datetime
    user.updated_at = datetime.now()
    db.commit()
    db.refresh(user)
    return user


@router.post("/upload-photo", summary="Upload foto profil")
def upload_profile_photo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload foto profil (jpg/png)."""
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Hanya jpg/png/webp yang diizinkan")

    upload_dir = "app/uploads/profile_photos"
    os.makedirs(upload_dir, exist_ok=True)

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    filename = f"user_{user.id}.{ext}"
    filepath = os.path.join(upload_dir, filename)

    try:
        with open(filepath, "wb") as buf:
            shutil.copyfileobj(file.file, buf)

        user.profile_photo_url = f"/uploads/profile_photos/{filename}"
        db.commit()
        db.refresh(user)

        return {"message": "Foto berhasil diupload", "url": user.profile_photo_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload gagal: {e}")
    finally:
        file.file.close()


@router.put("/change-password", summary="Ganti password")
def change_password(
    old_password: str,
    new_password: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Ganti password user yang sedang login."""
    from app.services.auth_service import verify_password, hash_password
    from app.models import UserAuth

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password baru minimal 8 karakter")

    user_auth = db.query(UserAuth).filter(UserAuth.user_id == user.id).first()
    if not user_auth or not verify_password(old_password, user_auth.password_hash):
        raise HTTPException(status_code=400, detail="Password lama tidak sesuai")

    user_auth.password_hash = hash_password(new_password)
    db.commit()
    return {"message": "Password berhasil diubah"}
