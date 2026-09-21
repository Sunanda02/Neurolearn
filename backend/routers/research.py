from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.security import get_current_user
from data.database import (
    complete_study_session,
    get_or_create_active_study_session,
    get_or_create_study_session_for_material,
    get_or_create_research_participant,
    get_study_session,
    record_completed_video,
    get_study_consent,
    set_study_consent,
    StudyConsentRequired,
)
from data.models_orm import User
from schemas.models import StudyConsentGrant, StudyConsentStatus


router = APIRouter(prefix="/api/research", tags=["Research Study"])


class CreateStudySessionRequest(BaseModel):
    course_id: str | None = None
    module_id: str | None = None
    video_id: str | None = None


class CompleteStudySessionRequest(BaseModel):
    completion_status: str = "completed"


class CompleteStudyVideoRequest(BaseModel):
    transcript_text: str = ""


# FIX (A-2): study-participation consent — separate from webcam consent
# (routers/attention.py). Checked as the single gate before any research
# record is created; see StudyConsentRequired / get_or_create_research_participant.

@router.get("/consent", response_model=StudyConsentStatus)
async def get_study_consent_status(current_user: User = Depends(get_current_user)):
    record = get_study_consent(current_user.id)
    if record is None:
        return StudyConsentStatus(student_id=current_user.id, granted=False)
    return StudyConsentStatus(**record)


@router.post("/consent", response_model=StudyConsentStatus)
async def grant_or_revoke_study_consent(
    grant: StudyConsentGrant,
    current_user: User = Depends(get_current_user),
):
    return StudyConsentStatus(**set_study_consent(current_user.id, grant.granted, grant.version))


@router.get("/participant")
async def get_participant(current_user: User = Depends(get_current_user)):
    try:
        return get_or_create_research_participant(current_user.id)
    except StudyConsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/study-sessions")
async def start_study_session(
    request: CreateStudySessionRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        return get_or_create_study_session_for_material(
            current_user.id,
            course_id=request.course_id,
            module_id=request.module_id,
            video_id=request.video_id,
        )
    except StudyConsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc))

@router.get("/study-sessions/active")
async def get_active_study_session(
    current_user: User = Depends(get_current_user),
):
    session = get_or_create_active_study_session(current_user.id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail="No active study session found.",
        )

    return session
@router.get("/study-sessions/{study_session_id}")
async def read_study_session(
    study_session_id: str,
    current_user: User = Depends(get_current_user),
):
    session = get_study_session(study_session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Study session not found")
    if session["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not your study session")
    return session


@router.post("/study-sessions/{study_session_id}/videos/{video_id}/complete")
async def complete_study_video(
    study_session_id: str,
    video_id: str,
    request: CompleteStudyVideoRequest,
    current_user: User = Depends(get_current_user),
):
    """Record a terminal video-completion event for assessment evidence."""
    try:
        return record_completed_video(
            study_session_id=study_session_id,
            user_id=current_user.id,
            video_id=video_id,
            transcript_text=request.transcript_text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/study-sessions/{study_session_id}/complete")
async def finish_study_session(
    study_session_id: str,
    request: CompleteStudySessionRequest,
    current_user: User = Depends(get_current_user),
):
    session = get_study_session(study_session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Study session not found")
    if session["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not your study session")
    if request.completion_status == "completed":
        raise HTTPException(
            status_code=409,
            detail="Study sessions are completed automatically after the tenth assessment response succeeds.",
        )
    return complete_study_session(study_session_id, request.completion_status)