"""
auth/security.py — password hashing and JWT for NeuroLearn's real auth system.

Uses the `bcrypt` library directly rather than passlib's CryptContext
wrapper: passlib 1.7.x has a known incompatibility with bcrypt>=4.1 (it
probes `bcrypt.__about__.__version__`, which no longer exists, and then
throws on the 72-byte truncation check) — calling bcrypt.hashpw /
bcrypt.checkpw directly sidesteps that entirely and is what passlib does
under the hood anyway.
"""
import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from data.db import get_db
from data.models_orm import User

# ── Config ──
# IMPORTANT: set JWT_SECRET to a real random value in any non-local
# deployment. This default is fine for local dev only — main.py logs a
# loud warning at startup if it's still set to this value.
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-insecure-secret-change-me")
JWT_ALGORITHM = "HS256"
# FIX (remaining-things request): previously 600 minutes (10h) with no
# revocation mechanism at all — a stolen/leaked token stayed valid for
# 10 hours no matter what. Now short-lived; REFRESH_TOKEN is what keeps
# the user logged in, and unlike the access token it CAN be revoked
# server-side (see RefreshToken model, /api/auth/logout).
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "30"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _hash_token(raw_token: str) -> str:
    """SHA-256 the raw token for at-rest storage — same rationale as not
    storing plaintext passwords: a DB read/leak shouldn't hand over a
    usable credential."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_raw_token() -> str:
    """A cryptographically random, URL-safe token for refresh/reset use."""
    return secrets.token_urlsafe(32)


# ── Password hashing ──

def hash_password(plain_password: str) -> str:
    # bcrypt has a hard 72-byte input limit; truncate defensively rather
    # than letting it raise on unusually long input.
    pw_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pw_bytes = plain_password.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(pw_bytes, hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed hash in storage — treat as verification failure, not a 500.
        return False


# ── JWT ──

def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


# ── FastAPI dependencies ──

def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Resolves the authenticated user from the Authorization: Bearer <token>
    header. Raises 401 if missing/invalid/expired, or if the user no
    longer exists. Every personal/mutating endpoint (profile, XP award,
    assessment submit, behavioral-cue snapshot, consent) depends on this
    instead of trusting a client-supplied student_id — the original code
    let any caller read or write any student's data by simply passing a
    different student_id, which this closes.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_exception
    user = db.get(User, user_id)
    if user is None:
        raise credentials_exception
    return user


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Same as get_current_user but returns None instead of raising —
    for endpoints that personalize when logged in but still work (e.g.
    a public leaderboard) without requiring it."""
    if not token:
        return None
    user_id = decode_access_token(token)
    if user_id is None:
        return None
    return db.get(User, user_id)
