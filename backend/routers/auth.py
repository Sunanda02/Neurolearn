"""
============================================================
ROUTER: Auth — Signup, Login, Refresh, Logout, Password Reset
Endpoints:
    POST /api/auth/signup
    POST /api/auth/login
    POST /api/auth/refresh
    POST /api/auth/logout
    GET  /api/auth/me
    POST /api/auth/request-password-reset
    POST /api/auth/reset-password
============================================================
Real accounts, real password hashing (bcrypt), real short-lived JWTs
plus revocable refresh tokens — replaces the hardcoded "student_001"
default that every other router previously used.
"""
from datetime import date, datetime, timedelta
import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from data.db import get_db
from data.database import (
    _user_to_dict,
    record_daily_activity,
    create_refresh_token,
    get_valid_refresh_token,
    revoke_refresh_token,
    revoke_all_refresh_tokens,
    create_password_reset_token,
    get_valid_password_reset_token,
    mark_password_reset_token_used,
    set_user_password,
)
from data.models_orm import User
from schemas.models import (
    SignupRequest, LoginRequest, TokenResponse, StudentProfile,
    RefreshRequest, RefreshResponse, LogoutRequest,
    RequestPasswordResetRequest, RequestPasswordResetResponse, ResetPasswordRequest,
)
from auth.security import (
    hash_password, verify_password, create_access_token, get_current_user,
    generate_raw_token, _hash_token,
    REFRESH_TOKEN_EXPIRE_DAYS, PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
)
from services.email_service import send_plain_email, is_email_configured

router = APIRouter(prefix="/api/auth", tags=["Auth"])
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


def _issue_tokens(user: User, db: Session) -> TokenResponse:
    access_token = create_access_token(subject=user.id)
    refresh_raw = generate_raw_token()
    create_refresh_token(
        user.id, _hash_token(refresh_raw),
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_raw,
        user=StudentProfile(**_user_to_dict(user, db)),
    )


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Create a new account. Returns a short-lived access token plus a
    longer-lived refresh token — the frontend should send the access
    token as `Authorization: Bearer <token>` and use POST /refresh with
    the refresh token once it expires."""
    existing = db.query(User).filter(User.email == request.email.lower().strip()).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    if len(request.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    user = User(
        email=request.email.lower().strip(),
        hashed_password=hash_password(request.password),
        name=request.name.strip() or request.email.split("@")[0],
        level=1, xp=0, xp_to_next_level=100,
        streak=0, best_streak=0,
        total_courses_completed=0, total_watch_time=0,
        badges=[], joined_date=date.today(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # FIX (remaining-things request): starts the streak at 1 instead of
    # leaving it permanently at 0 — nothing previously wrote to it at all.
    record_daily_activity(user.id)
    db.refresh(user)

    return _issue_tokens(user, db)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Verify email/password and return a fresh access + refresh token pair."""
    user = db.query(User).filter(User.email == request.email.lower().strip()).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    record_daily_activity(user.id)
    db.refresh(user)

    return _issue_tokens(user, db)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(request: RefreshRequest, db: Session = Depends(get_db)):
    """
    Exchange a still-valid refresh token for a new access token. The
    refresh token itself is ROTATED (the old one is revoked, a new one
    issued) — standard practice so a leaked refresh token has a limited
    window of use rather than being a permanent skeleton key.
    """
    token_hash = _hash_token(request.refresh_token)
    valid = get_valid_refresh_token(token_hash)
    if not valid:
        raise HTTPException(status_code=401, detail="Refresh token is invalid, expired, or already used")

    user = db.get(User, valid["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="Account no longer exists")

    revoke_refresh_token(token_hash)
    new_access = create_access_token(subject=user.id)
    new_refresh_raw = generate_raw_token()
    create_refresh_token(
        user.id, _hash_token(new_refresh_raw),
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return RefreshResponse(access_token=new_access, refresh_token=new_refresh_raw)


@router.post("/logout")
async def logout(request: LogoutRequest):
    """
    Revoke a refresh token server-side. FIX (remaining-things request):
    previously "logout" only meant the browser forgot its token — the
    token itself remained valid until natural expiry no matter what.
    This makes the token actually unusable immediately.
    """
    revoke_refresh_token(_hash_token(request.refresh_token))
    return {"message": "Logged out"}


@router.get("/me", response_model=StudentProfile)
async def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the authenticated user's own profile."""
    return StudentProfile(**_user_to_dict(current_user, db))


@router.post("/request-password-reset", response_model=RequestPasswordResetResponse)
async def request_password_reset(request: RequestPasswordResetRequest, db: Session = Depends(get_db)):
    """
    FIX (remaining-things request): password reset didn't exist at all
    before this. Always returns 200 with a generic message regardless of
    whether the email matches an account — NOT revealing account
    existence via response differences is standard practice for this
    endpoint (an attacker probing emails shouldn't learn which ones are
    registered).
    """
    generic_message = "If an account exists for that email, a reset link has been sent."
    user = db.query(User).filter(User.email == request.email.lower().strip()).first()
    if not user:
        return RequestPasswordResetResponse(message=generic_message)

    raw_token = generate_raw_token()
    create_password_reset_token(
        user.id, _hash_token(raw_token),
        expires_at=datetime.utcnow() + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
    )

    reset_link = f"{FRONTEND_URL}/reset-password?token={raw_token}"
    if is_email_configured():
        send_plain_email(
            user.email,
            "Reset your NeuroLearn password",
            f"Hi {user.name},\n\n"
            f"Use this link to reset your password (expires in {PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes):\n"
            f"{reset_link}\n\n"
            f"If you didn't request this, you can safely ignore this email.",
        )
        return RequestPasswordResetResponse(message=generic_message)

    # Dev fallback: no SMTP configured, so there's no other way for the
    # caller to get the token — return it directly rather than the
    # request silently going nowhere. Never do this with email configured.
    return RequestPasswordResetResponse(message=generic_message, dev_reset_token=raw_token)


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Complete a password reset given a valid, unexpired token. Revokes
    every existing refresh token for the account — a password reset
    should end every other logged-in session, not just leave them be."""
    if len(request.new_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    token_hash = _hash_token(request.token)
    valid = get_valid_password_reset_token(token_hash)
    if not valid:
        raise HTTPException(status_code=400, detail="Reset token is invalid or has expired")

    set_user_password(valid["user_id"], hash_password(request.new_password))
    mark_password_reset_token_used(token_hash)
    revoke_all_refresh_tokens(valid["user_id"])

    return {"message": "Password reset successfully. Please log in again."}
