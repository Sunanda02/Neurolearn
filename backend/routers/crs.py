"""
============================================================
ROUTER: CRS — Cognitive Readiness Score read endpoints
Phase 11 of the NeuroLearn-MCL implementation spec.

Endpoints:
    GET /api/crs/{student_id}                    — current (most recent) CRS
    GET /api/crs/{student_id}/history             — full CRS history
    GET /api/crs/{student_id}/performance/history — Performance (P) history
    GET /api/crs/{student_id}/attention/history   — Behavioral Cue (B) history
    GET /api/crs/{student_id}/integrity/history    — Integrity (I) history
    GET /api/crs/{student_id}/trend/history        — Trend (T) history
    GET /api/crs/{student_id}/complexity/history   — Complexity (C) history
    GET /api/crs/{student_id}/difficulty/reason    — latest adaptive explanation
============================================================

All endpoints are READ-only projections over the crs_history table
populated by routers/assessment.py's submit_assessment() (Phase 12). They
intentionally do not recompute anything — `ml/crs.py` is the only place
CRS math happens; this router just serves what's already been persisted.

FIX (auth request): every endpoint here previously took student_id as a
bare path parameter with no verification — anyone could read anyone's
full behavioral/performance history by enumerating IDs. All
eight now require the caller to be authenticated AND to be requesting
their own student_id (403 otherwise). There is no admin/instructor role
yet to justify broader access.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from data.database import (
    get_current_crs,
    get_crs_history,
    get_performance_history,
    get_behavioral_cue_history,
    get_integrity_history,
    get_trend_history,
    get_complexity_history,
)
from data.models_orm import User
from auth.security import get_current_user

router = APIRouter(prefix="/api/crs", tags=["Cognitive Readiness Score"])


def _require_self(student_id: str, current_user: User) -> None:
    if student_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only view your own CRS data")


@router.get("/{student_id}")
async def get_current_crs_endpoint(student_id: str, current_user: User = Depends(get_current_user)):
    """Most recent CRS record for a student (full component breakdown)."""
    _require_self(student_id, current_user)
    record = get_current_crs(student_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"No CRS history found for student '{student_id}' yet — "
                    "they need to complete at least one assessment.",
        )
    return record


@router.get("/{student_id}/history")
async def get_crs_history_endpoint(
    student_id: str,
    limit: Optional[int] = Query(default=None, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    """Full CRS history (every component + fused score), oldest-first."""
    _require_self(student_id, current_user)
    history = get_crs_history(student_id, limit=limit)
    return {"student_id": student_id, "count": len(history), "history": history}


@router.get("/{student_id}/performance/history")
async def performance_history(student_id: str, limit: Optional[int] = Query(default=None, ge=1, le=200), current_user: User = Depends(get_current_user)):
    _require_self(student_id, current_user)
    return {"student_id": student_id, "component": "performance", "history": get_performance_history(student_id, limit)}


@router.get("/{student_id}/attention/history")
async def behavioral_cue_history(student_id: str, limit: Optional[int] = Query(default=None, ge=1, le=200), current_user: User = Depends(get_current_user)):
    _require_self(student_id, current_user)
    return {"student_id": student_id, "component": "behavioral_cue", "history": get_behavioral_cue_history(student_id, limit)}


@router.get("/{student_id}/integrity/history")
async def integrity_history(student_id: str, limit: Optional[int] = Query(default=None, ge=1, le=200), current_user: User = Depends(get_current_user)):
    _require_self(student_id, current_user)
    return {"student_id": student_id, "component": "integrity", "history": get_integrity_history(student_id, limit)}


@router.get("/{student_id}/trend/history")
async def trend_history(student_id: str, limit: Optional[int] = Query(default=None, ge=1, le=200), current_user: User = Depends(get_current_user)):
    _require_self(student_id, current_user)
    return {"student_id": student_id, "component": "trend", "history": get_trend_history(student_id, limit)}


@router.get("/{student_id}/complexity/history")
async def complexity_history(student_id: str, limit: Optional[int] = Query(default=None, ge=1, le=200), current_user: User = Depends(get_current_user)):
    _require_self(student_id, current_user)
    return {"student_id": student_id, "component": "complexity", "history": get_complexity_history(student_id, limit)}


@router.get("/{student_id}/difficulty/reason")
async def difficulty_reason(student_id: str, current_user: User = Depends(get_current_user)):
    """Latest adaptive explanation string — what the dashboard's
    'why was this difficulty chosen' tooltip (Phase 13) reads from."""
    _require_self(student_id, current_user)
    record = get_current_crs(student_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No CRS history found for student '{student_id}' yet.")
    return {
        "student_id": student_id,
        "difficulty": record["difficulty"],
        "explanation": record["explanation"],
        "timestamp": record["timestamp"],
    }
