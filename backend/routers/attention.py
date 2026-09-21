"""
============================================================
ROUTER: Behavioral Cue — Camera-based behavioral-cue monitoring
Endpoints:
    GET  /api/attention/consent        — check consent status
    POST /api/attention/consent        — grant/revoke consent
    POST /api/attention/snapshot       — analyze a camera frame (consent-gated)
    GET  /api/attention/history        — get behavioral_cue log for a session
    POST /api/attention/purge-expired  — retention-window cleanup (CR6)
============================================================

CONSENT (CR6, peer review packet): this router previously analyzed and
logged every frame the frontend sent with no consent check, no retention
policy, and no opt-out path. `/snapshot` now refuses to run the ML model
or write anything to the behavioral_cue log unless a prior `granted=True`
consent record exists for that student_id AND the request itself carries
`consent_confirmed=True` (belt-and-suspenders: the frontend gates camera
start on consent, this is the server-side enforcement of the same rule).
Declining consent must not silently zero-out or otherwise penalize CRS —
`ml/crs.py` already defaults Behavioral Cue (B) to a neutral 0.5 when no
attention_score_pct is supplied, so opting out only removes the *bonus*
signal, it never forces "easy" or "hard".
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from starlette.concurrency import run_in_threadpool
from schemas.models import (
    AttentionSnapshot,
    AttentionFrameRequest,
    ConsentGrant,
    ConsentStatus,
)
from ml import attention_detector
from ml.attention_model import get_session_detector
from data.database import (
    log_attention,
    get_attention_logs,
    get_consent,
    set_consent,
    purge_expired_attention_logs,
    get_study_session,
)
from data.models_orm import User
from auth.security import get_current_user

router = APIRouter(prefix="/api/attention", tags=["Behavioral Cue"])


def _analyze_frame_on_detector(user_id: str, session_id: str, frame_base64: str) -> dict:
    """Runs entirely off the event loop via run_in_threadpool (see /snapshot
    below) — acquires this (student, session_id)'s isolated detector (B-4)
    and analyzes one frame. Bundled into one function so both the
    detector lookup (cheap after the first call, but does a MediaPipe
    FaceMesh cold-init on the first) and the analysis itself stay off the
    event loop."""
    detector = get_session_detector(user_id, session_id)
    return detector.analyze_frame(frame_base64)


@router.get("/consent", response_model=ConsentStatus)
async def get_consent_status(session_id: str, current_user: User = Depends(get_current_user)):
    """Return the current webcam-monitoring consent status for the authenticated student."""
    record = get_consent(current_user.id, session_id)
    if record is None:
        return ConsentStatus(student_id=current_user.id, session_id=session_id, granted=False)
    return ConsentStatus(**record)


@router.post("/consent", response_model=ConsentStatus)
async def grant_or_revoke_consent(
    grant: ConsentGrant,
    current_user: User = Depends(get_current_user),
):
    """
    Record the authenticated student's consent decision for webcam-based
    behavioral-cue monitoring. Called by the frontend ConsentModal before the
    camera is ever started, and again if the student later revokes
    consent from their profile/privacy settings. `grant.student_id` is
    ignored for authorization — consent is always recorded against the
    JWT-identified student, never an arbitrary id the client supplies.
    """
    if grant.study_session_id:
        study = get_study_session(grant.study_session_id)
        if not study or study["user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="Invalid study session for consent")

    record = {
        "student_id": current_user.id,
        "session_id": grant.session_id,
        "study_session_id": grant.study_session_id,
        "granted": grant.granted,
        "granted_at": datetime.now(timezone.utc).isoformat(),
        "retention_days": grant.retention_days,
        "raw_frames_stored": grant.raw_frames_stored,
        "version": grant.version,
    }
    set_consent(record)
    return ConsentStatus(**record)


@router.post("/snapshot", response_model=AttentionSnapshot)
async def analyze_frame(
    request: AttentionFrameRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Analyze a camera frame for the authenticated student's behavioral_cue.
    Consent-gated (CR6): returns 403 rather than analyzing or logging
    anything if the student has not granted consent, or if the request
    doesn't carry consent_confirmed=True.

    JSON Response:
    {
        "timestamp": "...",
        "score": 85,
        "state": "attentive",
        "confidence": 0.92,
        "message": "Camera-derived behavioural signal: high band.",
        "model_response": {
            "eye_contact": 0.88,
            "head_pose": "forward",
            "face_detected": true,
            "blink_rate": 15.0
        },
        "source": "live",
        "consent_confirmed": true
    }
    """
    consent_record = get_consent(current_user.id, request.session_id)
    consent_on_file = bool(
        consent_record
        and consent_record.get("granted")
        and consent_record.get("session_id") == request.session_id
    )

    if not (request.consent_confirmed and consent_on_file):
        raise HTTPException(
            status_code=403,
            detail=(
                "Webcam behavioral-cue monitoring requires recorded consent. "
                "Call POST /api/attention/consent with granted=true and the "
                "current session_id first, then resend this request with the "
                "same session_id and consent_confirmed=true."
            ),
        )

    # Run ML model (frame is analyzed in-memory and never persisted raw —
    # only the derived score/sub-metrics below are written to storage).
    # FIX (B-4): each (student, session_id) pair gets its own isolated
    # detector instance — never the shared `attention_detector` singleton —
    # so blink timestamps, smoothing, and other temporal state can't leak
    # between learners or sessions.
    #
    # FIX (attention-blocked-during-transcription): this used to call
    # get_session_detector()/analyze_frame() directly and synchronously —
    # the only CPU-bound handler in the backend that did, while every
    # transcription route (routers/transcription.py) was already
    # deliberately offloaded to a worker thread for exactly this reason
    # (see that file's docstrings). A synchronous call here blocks FastAPI's
    # single event loop for the full MediaPipe inference duration, which
    # also delays dispatching *any other* incoming request — including the
    # transcription fetch that fires the moment a video starts playing —
    # even though that other work is itself already thread-offloaded, since
    # it still has to be accepted/dispatched by this same event loop first.
    # run_in_threadpool here mirrors the same pattern already used for
    # transcription, with no change to what analyze_frame does or returns.
    result = await run_in_threadpool(
        _analyze_frame_on_detector,
        current_user.id, request.session_id, request.frame_base64,
    )
    result["consent_confirmed"] = True

    if request.study_session_id:
        study = get_study_session(request.study_session_id)
        if not study or study["user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="Invalid study session for webcam snapshot")

    # Log only the derived score, under the retention window the student
    # consented to (see purge_expired_attention_logs / CR6).
    log_attention({
        "video_id": request.video_id,
        "session_id": request.session_id,
        "study_session_id": request.study_session_id,
        "student_id": current_user.id,
        **result,
    })

    return result


@router.post("/purge-expired")
async def purge_expired(current_user: User = Depends(get_current_user)):
    """
    Delete attention_logs entries older than each student's consented
    retention window (default 30 days). Intended to run on a schedule;
    exposed as a manual endpoint for the prototype since there is no
    background job runner yet.

    FIX (B-5): this used to be callable with no authentication at all —
    any anonymous caller could trigger retention purges. It now requires
    a valid session like every other research-data-touching endpoint in
    this router. (There is no admin/staff role in this app yet — every
    account is a student account — so this is authentication, not
    authorization to a privileged role; narrowing who among authenticated
    users may purge is a research-role decision outside this item's scope.)
    """
    removed = purge_expired_attention_logs()
    return {"removed": removed}


@router.get("/history")
async def get_attention_history(video_id: str, current_user: User = Depends(get_current_user)):
    """Get behavioral-cue logs for a video watching session (your own only)."""
    logs = get_attention_logs(video_id, current_user.id)
    return {
        "video_id": video_id,
        "student_id": current_user.id,
        "total_snapshots": len(logs),
        "logs": logs,
        "average_score": (
            sum(l.get("score", 0) for l in logs) / max(len(logs), 1)
        ),
    }


@router.get("/dummy-snapshot", response_model=AttentionSnapshot)
async def get_dummy_snapshot(current_user: User = Depends(get_current_user)):
    """
    Get a dummy behavioral-cue snapshot (no camera required).
    Useful for testing the frontend without webcam.

    FIX (B-5): this used to be callable with no authentication, making a
    research-capable endpoint anonymously reachable. G0 development use of
    a dummy snapshot is still permitted (this never touches research
    storage — it doesn't call log_attention), but it now requires a valid
    logged-in session like the rest of this router, rather than being
    open to anyone.
    """
    return attention_detector._generate_dummy_snapshot(
        __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime())
    )