"""Authentication and JWT token management"""
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.models import User, UserAuth
from app.schemas import UserRegister, UserLogin, TokenResponse
from app.database import get_db
import os

SECRET_KEY = os.getenv("SECRET_KEY", "GANTI_INI_DI_PRODUCTION")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer_scheme = HTTPBearer()


# ── Password Utilities ─────────────────────────────────────────

def hash_password(password: str) -> str:
    try:
        return pwd_context.hash(password)
    except Exception as e:
        raise ValueError(f"Gagal memproses password: {e}")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


# ── JWT Utilities ──────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("sub") is None:
            return None
        return payload
    except JWTError:
        return None


# ── User CRUD ──────────────────────────────────────────────────

def register_user(db: Session, user_data: UserRegister) -> User:
    if db.query(User).filter(User.email == user_data.email).first():
        raise ValueError("Email sudah terdaftar")

    new_user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        phone_number=user_data.phone_number,
        greenhouse_location=user_data.greenhouse_location,
        address=user_data.address,
    )
    db.add(new_user)
    db.flush()

    db.add(UserAuth(user_id=new_user.id, password_hash=hash_password(user_data.password)))
    db.commit()
    db.refresh(new_user)
    return new_user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    user_auth = db.query(UserAuth).filter(UserAuth.user_id == user.id).first()
    if not user_auth or not verify_password(password, user_auth.password_hash):
        return None
    return user


def login_user(db: Session, login_data: UserLogin) -> TokenResponse:
    user = authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise ValueError("Email atau password salah")

    return TokenResponse(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
        token_type="bearer",
    )


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


# ── FastAPI Dependency ─────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency — pakai di semua endpoint yang butuh login:

        from app.services.auth_service import get_current_user

        @router.get("/me")
        def me(user: User = Depends(get_current_user)):
            return user
    """
    payload = verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak valid atau sudah expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_id(db, int(payload["sub"]))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User tidak ditemukan",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
