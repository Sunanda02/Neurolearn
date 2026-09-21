"""
============================================================
ROUTER: Gamification — Leaderboard, Challenges, Notifications
Endpoints:
    GET /api/leaderboard        (public — real, live query, see below)
    GET /api/challenges/daily   (public — global content)
    GET /api/notifications      (auth required — your own)
============================================================
FIX (real leaderboard request): /api/leaderboard previously returned a
static, hand-seeded TinyDB table of fictional students (Priya Sharma,
Marcus Chen, ...) that never changed regardless of what any real student
did. It now runs a live `ORDER BY xp DESC` over the real `users` table
(see data/database.py's get_leaderboard()), so completing an assessment
and earning XP (routers/assessment.py's _apply_xp) actually moves your
position on it.
"""

from fastapi import APIRouter, Depends, HTTPException
from schemas.models import LeaderboardEntry, DailyChallenge, Notification
from data.database import get_leaderboard, get_daily_challenges, get_notifications, advance_challenge_progress
from data.models_orm import User
from auth.security import get_current_user

router = APIRouter(prefix="/api", tags=["Gamification"])


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
async def leaderboard():
    """Public, real leaderboard — ranked live by actual XP in Postgres."""
    return get_leaderboard()


@router.get("/challenges/daily", response_model=list[DailyChallenge])
async def daily_challenges(current_user: User = Depends(get_current_user)):
    """
    Get today's daily challenges with the AUTHENTICATED STUDENT'S OWN
    progress. FIX (remaining-things request): previously one shared
    completed/progress value existed per challenge — one student
    finishing "Watch 30 minutes" marked it finished for every student.
    """
    return get_daily_challenges(current_user.id)


VALID_PROGRESS_TYPES = {"watch", "review"}


@router.post("/challenges/daily/{challenge_type}/progress")
async def bump_challenge_progress(
    challenge_type: str,
    amount: int = 1,
    current_user: User = Depends(get_current_user),
):
    """
    Manually advance progress on challenges of a given type for today
    (e.g. "watch" when a video-watch-time milestone is hit, "review" when
    a completed lesson is revisited). "quiz" and "streak" progress are
    NOT accepted here — those are advanced automatically by
    routers/assessment.py's submit_assessment and routers/auth.py's
    login respectively, so a client can't fake completing them.
    """
    if challenge_type not in VALID_PROGRESS_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"challenge_type must be one of {sorted(VALID_PROGRESS_TYPES)} "
                    "— 'quiz' and 'streak' progress is server-driven only.",
        )
    if amount < 1 or amount > 120:
        raise HTTPException(status_code=422, detail="amount must be between 1 and 120")
    newly_completed = advance_challenge_progress(current_user.id, challenge_type, amount=amount)
    return {"newly_completed": newly_completed}


@router.get("/notifications", response_model=list[Notification])
async def notifications(current_user: User = Depends(get_current_user)):
    """Get notifications for the authenticated student."""
    return get_notifications(current_user.id)
