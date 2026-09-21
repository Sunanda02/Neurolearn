"""
data/database.py — Postgres-backed data access layer.

FIX (auth/postgres/xp/leaderboard request): this file previously wrote to
a TinyDB JSON file (data/database_tinydb_legacy.py, kept for reference)
despite the manuscript claiming "PostgreSQL-backed persistence" — a real
claim-vs-implementation gap. This version is backed by an actual Postgres
database (see data/db.py) via SQLAlchemy.

Function names and return shapes are kept as close as possible to the
legacy TinyDB version so the routers that import from this module did
not all need to be rewritten — only the handful that needed real
authentication or that were silently not persisting XP were changed
(routers/student.py, routers/assessment.py, routers/gamification.py,
routers/auth.py — new).
"""
from typing import Optional
from datetime import datetime, date, timedelta
import statistics
import subprocess
from pathlib import Path

from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from data.db import SessionLocal
from data.models_orm import (
    User, Course, AutoCourse, AssessmentSession, AssessmentResult,
    CRSHistory, Consent, StudyConsent, AttentionLog, DailyChallenge, Notification,
    DailyChallengeProgress, PasswordResetToken, RefreshToken,
    ResearchParticipant, StudySession, QuestionResponse, ResearchCRSDecision,
    ResearchLegacyDecision,
    BehavioralSummary, PrePostResult, GeneratedQuestion, StudyVideoCompletion,
    VideoTranscriptCache,
)

XP_PER_LEVEL = 100
EXPERIMENT_VERSION = "full-study-v2-mixed-segments"
CRS_CONFIG_VERSION = "crs-equal-weights-v1"
MIXED_METHOD_CONDITION = "MIXED"
FIXED_METHOD_SEQUENCE = "MCRF_THEN_LEGACY"
VALID_STUDY_CONDITIONS = {"MCRF", "LEGACY", MIXED_METHOD_CONDITION}
VALID_SEQUENCE_ORDERS = {"MCRF_THEN_LEGACY", "LEGACY_THEN_MCRF"}


class StudyConsentRequired(Exception):
    """
    FIX (A-2): raised by get_or_create_research_participant() — the root
    creation point for ResearchParticipant/StudySession rows — when no
    granted study_consent record exists for this user. Every research
    write downstream (assessment responses, prepost results, CRS
    decisions, video completions) is keyed to a study_session_id that can
    only exist if a StudySession was created, which can only happen
    through this function, so gating here gates all of them. Routers
    catch this and return 403; they must not swallow it and proceed.
    """
    pass


def level_from_xp(xp: int) -> int:
    return max(1, int(xp or 0) // XP_PER_LEVEL + 1)


def xp_to_next_level(xp: int) -> int:
    return XP_PER_LEVEL - (int(xp or 0) % XP_PER_LEVEL)


def apply_xp(user: User, amount: int) -> dict:
    before_level = level_from_xp(user.xp)
    user.xp = max(0, int(user.xp or 0) + int(amount or 0))
    user.level = level_from_xp(user.xp)
    user.xp_to_next_level = xp_to_next_level(user.xp)
    return {
        "new_xp": user.xp,
        "new_level": user.level,
        "leveled_up": user.level > before_level,
        "xp_to_next_level": user.xp_to_next_level,
    }


def _session() -> Session:
    """Short-lived session for the simple functions below (mirrors the
    original TinyDB functions' style of "just do the operation and
    return" with no explicit session threading through every call site)."""
    return SessionLocal()


def current_application_version() -> Optional[str]:
    try:
        repo_root = Path(__file__).resolve().parents[2]
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def _participant_number(participant_id: str) -> int:
    try:
        return int(participant_id.rsplit("_", 1)[1])
    except Exception:
        return 0


def get_study_consent(user_id: str, db: Optional[Session] = None) -> Optional[dict]:
    """FIX (A-2): look up the current study-participation consent record."""
    owns_session = db is None
    db = db or _session()
    try:
        row = db.get(StudyConsent, user_id)
        if row is None:
            return None
        return {
            "student_id": row.student_id,
            "granted": bool(row.granted),
            "granted_at": row.granted_at.isoformat() if row.granted_at else None,
            "version": row.version,
        }
    finally:
        if owns_session:
            db.close()


def set_study_consent(user_id: str, granted: bool, version: str = "1.0") -> dict:
    """FIX (A-2): record the authenticated student's study-participation
    consent decision. This is independent of webcam consent."""
    db = _session()
    try:
        row = db.get(StudyConsent, user_id)
        now = datetime.utcnow()
        if row is None:
            row = StudyConsent(
                student_id=user_id, granted=granted, granted_at=now, version=version,
            )
            db.add(row)
        else:
            row.granted = granted
            row.granted_at = now
            row.version = version
        db.commit()
        return {
            "student_id": user_id,
            "granted": granted,
            "granted_at": now.isoformat(),
            "version": version,
        }
    finally:
        db.close()


def _next_participant_id(db: Session) -> str:
    rows = db.execute(select(ResearchParticipant.participant_id)).all()
    max_seen = max((_participant_number(r[0]) for r in rows), default=0)
    return f"participant_{max_seen + 1:03d}"


def _assigned_condition_for_participant_id(participant_id: str) -> str:
    # The actual study is within-subject: every participant receives both
    # methods in one assessment.  Keep the legacy field for historical rows,
    # but make its value truthful for newly created study records.
    return MIXED_METHOD_CONDITION


def get_or_create_research_participant(user_id: str, db: Optional[Session] = None) -> dict:
    owns_session = db is None
    db = db or _session()
    try:
        row = db.execute(
            select(ResearchParticipant).where(ResearchParticipant.user_id == user_id)
        ).scalar_one_or_none()
        if row is None:
            # FIX (A-2): this is the root creation point for research
            # records. Independently verify study-participation consent
            # server-side before creating anything — never trust a
            # client-supplied flag. (Reading an *existing* participant
            # below is not gated here; only creation is.)
            consent = get_study_consent(user_id, db)
            if not (consent and consent.get("granted")):
                raise StudyConsentRequired(
                    "Study-participation consent is required before a research "
                    "record can be created for this student."
                )
            participant_id = _next_participant_id(db)
            sequence_order = FIXED_METHOD_SEQUENCE
            row = ResearchParticipant(
                participant_id=participant_id,
                user_id=user_id,
                sequence_order=sequence_order,
                assigned_condition=_assigned_condition_for_participant_id(participant_id),
            )
            db.add(row)
            db.flush()
            if owns_session:
                db.commit()
        else:
            # New sessions always follow the same within-assessment order;
            # participant-level A/B assignment is no longer part of the
            # protocol.  Existing completed study_sessions retain their own
            # historical condition/sequence values.
            row.sequence_order = FIXED_METHOD_SEQUENCE
            row.assigned_condition = MIXED_METHOD_CONDITION
            db.flush()
            if owns_session:
                db.commit()
        return {
            "participant_id": row.participant_id,
            "user_id": row.user_id,
            "sequence_order": row.sequence_order,
            "assigned_condition": row.assigned_condition,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
    finally:
        if owns_session:
            db.close()


def create_study_session(
    user_id: str,
    course_id: Optional[str] = None,
    video_id: Optional[str] = None,
    module_id: Optional[str] = None,
) -> dict:
    db = _session()
    try:
        participant_doc = get_or_create_research_participant(user_id, db)
        participant = db.get(ResearchParticipant, participant_doc["participant_id"])
        participant.sequence_order = FIXED_METHOD_SEQUENCE
        participant.assigned_condition = MIXED_METHOD_CONDITION
        condition = MIXED_METHOD_CONDITION
        row = StudySession(
            participant_id=participant.participant_id,
            user_id=user_id,
            condition=condition,
            sequence_order=FIXED_METHOD_SEQUENCE,
            course_id=course_id,
            module_id=module_id or course_id,
            video_id=video_id,
            experiment_version=EXPERIMENT_VERSION,
            application_version=current_application_version(),
            crs_config_version=CRS_CONFIG_VERSION,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return study_session_to_dict(row)
    finally:
        db.close()


def get_or_create_study_session_for_material(
    user_id: str,
    course_id: Optional[str] = None,
    video_id: Optional[str] = None,
    module_id: Optional[str] = None,
) -> dict:
    db = _session()
    try:
        existing = db.execute(
            select(StudySession)
            .where(
                StudySession.user_id == user_id,
                StudySession.course_id == course_id,
                StudySession.experiment_version == EXPERIMENT_VERSION,
                StudySession.completion_status == "started",
            )
            .order_by(StudySession.started_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if existing:
            return study_session_to_dict(existing)
    finally:
        db.close()
    return create_study_session(user_id, course_id=course_id, video_id=video_id, module_id=module_id)


def get_study_session(study_session_id: str) -> Optional[dict]:
    db = _session()
    try:
        row = db.get(StudySession, study_session_id)
        return study_session_to_dict(row) if row else None
    finally:
        db.close()


def get_or_create_active_study_session(
    user_id: str,
    course_id: Optional[str] = None,
    video_id: Optional[str] = None,
    requested_study_session_id: Optional[str] = None,
) -> dict:
    db = _session()
    try:
        if requested_study_session_id:
            existing = db.get(StudySession, requested_study_session_id)
            if not existing or existing.user_id != user_id:
                raise ValueError("Invalid study_session_id for current user")
            return study_session_to_dict(existing)

        existing = db.execute(
            select(StudySession)
            .where(
                StudySession.user_id == user_id,
                StudySession.experiment_version == EXPERIMENT_VERSION,
                StudySession.completion_status == "started",
            )
            .order_by(StudySession.started_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if existing:
            if course_id and not existing.course_id:
                existing.course_id = course_id
            if video_id and not existing.video_id:
                existing.video_id = video_id
            db.commit()
            return study_session_to_dict(existing)
    finally:
        db.close()
    return create_study_session(user_id, course_id=course_id, video_id=video_id)


def complete_study_session(study_session_id: str, status: str = "completed") -> Optional[dict]:
    db = _session()
    try:
        row = db.get(StudySession, study_session_id)
        if not row:
            return None
        row.completion_status = status
        row.ended_at = datetime.utcnow()
        if row.pretest_score is not None and row.posttest_score is not None:
            row.learning_gain = row.posttest_score - row.pretest_score
        db.commit()
        db.refresh(row)
        return study_session_to_dict(row)
    finally:
        db.close()


def study_session_to_dict(row: StudySession) -> dict:
    return {
        "study_session_id": row.study_session_id,
        "participant_id": row.participant_id,
        "user_id": row.user_id,
        "condition": row.condition,
        "sequence_order": row.sequence_order,
        "course_id": row.course_id,
        "module_id": row.module_id,
        "video_id": row.video_id,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        "completion_status": row.completion_status,
        "experiment_version": row.experiment_version,
        "application_version": row.application_version,
        "crs_config_version": row.crs_config_version,
        "pretest_score": row.pretest_score,
        "posttest_score": row.posttest_score,
        "learning_gain": row.learning_gain,
        "camera_used": row.camera_used,
        "camera_opted_out": row.camera_opted_out,
        "camera_revoked": row.camera_revoked,
    }


def record_completed_video(
    study_session_id: str,
    user_id: str,
    video_id: str,
    transcript_text: Optional[str] = None,
) -> dict:
    """Persist one completed video without treating an opened video as done.

    The client calls this only from a terminal playback event.  Repeating a
    completion event is intentionally idempotent and may enrich a previously
    empty transcript, but never changes the original order or timestamp.
    """
    db = _session()
    try:
        study = db.get(StudySession, study_session_id)
        if not study or study.user_id != user_id:
            raise ValueError("Invalid study_session_id for current user")
        if study.completion_status != "started":
            raise ValueError("Study session is no longer accepting completed videos")
        if not video_id:
            raise ValueError("video_id is required")

        existing = db.execute(
            select(StudyVideoCompletion).where(
                StudyVideoCompletion.study_session_id == study_session_id,
                StudyVideoCompletion.video_id == video_id,
            )
        ).scalar_one_or_none()
        if existing is None:
            next_order = int(
                db.execute(
                    select(func.count(StudyVideoCompletion.id)).where(
                        StudyVideoCompletion.study_session_id == study_session_id
                    )
                ).scalar_one()
                or 0
            ) + 1
            existing = StudyVideoCompletion(
                study_session_id=study_session_id,
                participant_id=study.participant_id,
                video_id=video_id,
                completion_order=next_order,
                transcript_text=(transcript_text or None),
            )
            db.add(existing)
            if not study.video_id:
                study.video_id = video_id
        elif transcript_text and not (existing.transcript_text or "").strip():
            existing.transcript_text = transcript_text

        db.commit()
        db.refresh(existing)
        return {
            "study_session_id": study_session_id,
            "video_id": existing.video_id,
            "completion_order": existing.completion_order,
            "completed_at": existing.completed_at.isoformat(),
        }
    finally:
        db.close()


def get_completed_video_context(study_session_id: str) -> dict:
    """Return the ordered, server-recorded material eligible for assessment."""
    db = _session()
    try:
        rows = db.execute(
            select(StudyVideoCompletion)
            .where(StudyVideoCompletion.study_session_id == study_session_id)
            .order_by(StudyVideoCompletion.completion_order.asc())
        ).scalars().all()
        return {
            "contributing_video_ids": [row.video_id for row in rows],
            "transcript_text": "\n\n".join(
                f"[Video {row.video_id}]\n{row.transcript_text.strip()}"
                for row in rows
                if row.transcript_text and row.transcript_text.strip()
            ),
            "videos": [
                {
                    "video_id": row.video_id,
                    "completion_order": row.completion_order,
                    "completed_at": row.completed_at.isoformat(),
                    "transcript_present": bool(row.transcript_text and row.transcript_text.strip()),
                }
                for row in rows
            ],
        }
    finally:
        db.close()


def get_completed_video_behavioral_score(study_session_id: str) -> Optional[float]:
    """Average only observations for videos actually completed in this study.

    FIX (D-4 follow-up): this used to return 50.0 for "no completed videos"
    and "no attention logs" alike — indistinguishable from a genuine 50%
    measurement by the time it reached compute_crs(). That silently
    defeated the behavioral_cue source flag added in ml/crs.py (SAP
    section 9's "source flags" requirement): a student who never granted
    camera consent looked identical, in the stored decision record, to
    one whose camera genuinely measured 50%. Returns None for "no genuine
    data" instead — callers (adaptive_engine / compute_crs) already treat
    None as "apply the documented neutral default and flag it as such."
    """
    db = _session()
    try:
        completed_ids = {
            row[0]
            for row in db.execute(
                select(StudyVideoCompletion.video_id).where(
                    StudyVideoCompletion.study_session_id == study_session_id
                )
            ).all()
        }
        if not completed_ids:
            return None
        logs = db.execute(
            select(AttentionLog).where(AttentionLog.study_session_id == study_session_id)
        ).scalars().all()
        scores = [float(log.score) for log in logs if log.video_id in completed_ids and log.score is not None]
        return sum(scores) / len(scores) if scores else None
    finally:
        db.close()


# ── Persistent video transcript cache ──────────────────────
# Global, video_url-keyed cache of real Whisper transcripts (see
# ml/transcription_model.py), separate from StudyVideoCompletion above:
# StudyVideoCompletion.transcript_text is the session-scoped record of
# what a specific student watched/completed in a specific study session;
# this table is a single, session-independent row per video_url so the
# same educational video isn't re-downloaded/re-transcribed every time a
# different student (or a restarted backend) needs it again.

def get_cached_video_transcript(video_url: str) -> Optional[list[dict]]:
    """Look up a persisted real transcript by video URL.

    Returns the exact segment list previously saved by
    save_video_transcript (same shape produced by Faster-Whisper: id,
    text, timestamp, start_time, end_time, confidence, model_response),
    or None if this video has never been successfully transcribed and
    persisted before.
    """
    db = _session()
    try:
        row = db.get(VideoTranscriptCache, video_url)
        if not row or not row.segments:
            return None
        return row.segments
    finally:
        db.close()


def save_video_transcript(video_url: str, segments: list[dict]) -> None:
    """Persist a successfully-produced real transcript so it survives a
    backend restart. Upserts on video_url (the primary key), so calling
    this more than once for the same video updates the one existing row
    rather than creating a duplicate.
    """
    db = _session()
    try:
        db.merge(VideoTranscriptCache(video_url=video_url, segments=segments))
        db.commit()
    finally:
        db.close()


# ── Users / Students ────────────────────────────────────────
# NOTE: "student" and "user" are the same row (see models_orm.User) —
# every account created via /api/auth/signup is a student profile.

def _user_to_dict(user: User, db: Session) -> dict:
    """Shape a User row into the same dict shape StudentProfile expects,
    including a live-computed `rank` (position in the real leaderboard —
    see get_leaderboard) rather than a stored, staleable rank field."""
    rank = _compute_rank(db, user.id)
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "avatar": user.avatar,
        "level": level_from_xp(user.xp),
        "xp": user.xp,
        "xp_to_next_level": xp_to_next_level(user.xp),
        "streak": user.streak,
        "best_streak": user.best_streak,
        "total_courses_completed": user.total_courses_completed,
        "total_watch_time": user.total_watch_time,
        "joined_date": user.joined_date.isoformat() if isinstance(user.joined_date, date) else str(user.joined_date),
        "rank": rank,
        "badges": user.badges or [],
    }


def _compute_rank(db: Session, student_id: str) -> int:
    """1-indexed position of student_id in the real, live XP ordering —
    replaces the old static `rank` field that was seeded once and never
    recalculated as XP changed."""
    ids_by_xp = [
        row[0] for row in db.execute(
            select(User.id).order_by(User.xp.desc())
        ).all()
    ]
    try:
        return ids_by_xp.index(student_id) + 1
    except ValueError:
        return len(ids_by_xp) + 1


def get_student(student_id: str) -> Optional[dict]:
    db = _session()
    try:
        user = db.get(User, student_id)
        return _user_to_dict(user, db) if user else None
    finally:
        db.close()


def update_student(student_id: str, updates: dict):
    db = _session()
    try:
        user = db.get(User, student_id)
        if not user:
            return
        for k, v in updates.items():
            setattr(user, k, v)
        db.commit()
    finally:
        db.close()


# ── Courses ──────────────────────────────────────────────────

def get_all_courses() -> list[dict]:
    db = _session()
    try:
        rows = db.execute(select(Course)).scalars().all()
        return [_course_to_dict(c) for c in rows]
    finally:
        db.close()


def get_course(course_id: str) -> Optional[dict]:
    db = _session()
    try:
        c = db.get(Course, course_id)
        return _course_to_dict(c) if c else None
    finally:
        db.close()


def _course_to_dict(c: Course) -> dict:
    return {
        "id": c.id, "title": c.title, "description": c.description,
        "icon": c.icon, "category": c.category, "difficulty": c.difficulty,
        "total_videos": c.total_videos, "completed_videos": c.completed_videos,
        "progress": c.progress, "estimated_hours": c.estimated_hours,
        "tags": c.tags or [], "video_links": c.video_links or [],
    }


# ── Assessment sessions/results ─────────────────────────────

def save_assessment_session(session: dict):
    db = _session()
    try:
        row = AssessmentSession(
            id=session["id"],
            student_id=session["student_id"],
            study_session_id=session.get("study_session_id"),
            participant_id=session.get("participant_id"),
            condition=session.get("condition"),
            course_id=session.get("course_id"),
            video_id=session.get("video_id"),
            contributing_video_ids=session.get("contributing_video_ids", []),
            questions=session.get("questions", []),
            difficulty=session.get("difficulty", "medium"),
            starting_difficulty=session.get("starting_difficulty", session.get("difficulty", "medium")),
            selected_difficulty=session.get("selected_difficulty", session.get("difficulty", "medium")),
            completion_status=session.get("completion_status", "started"),
            number_of_questions=len(session.get("questions", [])),
            time_limit=session.get("time_limit", 420),
            attention_score_during_video=session.get("attention_score_during_video", 50),
            transcript_text=session.get("transcript_text"),
            adaptive_state=session.get("adaptive_state", {}),
        )
        db.merge(row)
        db.commit()
    finally:
        db.close()


def get_assessment_session(session_id: str) -> Optional[dict]:
    db = _session()
    try:
        s = db.get(AssessmentSession, session_id)
        if not s:
            return None
        return {
            "id": s.id, "student_id": s.student_id, "questions": s.questions or [],
            "study_session_id": s.study_session_id,
            "participant_id": s.participant_id,
            "condition": s.condition,
            "course_id": s.course_id,
            "video_id": s.video_id,
            "contributing_video_ids": s.contributing_video_ids or [],
            "difficulty": s.difficulty, "time_limit": s.time_limit,
            "starting_difficulty": s.starting_difficulty or s.difficulty,
            "selected_difficulty": s.selected_difficulty or s.difficulty,
            "completion_status": s.completion_status,
            "attention_score_during_video": s.attention_score_during_video,
            "transcript_text": s.transcript_text,
            "adaptive_state": s.adaptive_state or {},
            "adaptive_metadata": (s.adaptive_state or {}).get("adaptive_metadata", {
                "previous_score": None,
                "adjusted_difficulty": s.difficulty,
                "reason": "Assessment protocol initialized.",
            }),
        }
    finally:
        db.close()


def get_canonical_assessment_session_for_study(study_session_id: str) -> Optional[dict]:
    db = _session()
    try:
        rows = db.execute(
            select(AssessmentSession)
            .where(AssessmentSession.study_session_id == study_session_id)
            .order_by(AssessmentSession.created_at.desc())
        ).scalars().all()
        row = next((candidate for candidate in rows if candidate.questions), None) or (rows[0] if rows else None)
        if not row:
            return None
        return {
            "id": row.id, "student_id": row.student_id, "questions": row.questions or [],
            "study_session_id": row.study_session_id,
            "participant_id": row.participant_id,
            "condition": row.condition,
            "course_id": row.course_id,
            "video_id": row.video_id,
            "contributing_video_ids": row.contributing_video_ids or [],
            "difficulty": row.difficulty, "time_limit": row.time_limit,
            "starting_difficulty": row.starting_difficulty or row.difficulty,
            "selected_difficulty": row.selected_difficulty or row.difficulty,
            "completion_status": row.completion_status,
            "attention_score_during_video": row.attention_score_during_video,
            "transcript_text": row.transcript_text,
            "adaptive_state": row.adaptive_state or {},
            "adaptive_metadata": (row.adaptive_state or {}).get("adaptive_metadata", {
                "previous_score": None,
                "adjusted_difficulty": row.difficulty,
                "reason": "Assessment protocol initialized.",
            }),
        }
    finally:
        db.close()


def save_assessment_result(result: dict):
    db = _session()
    try:
        known = {"id", "student_id", "session_id", "score", "percentage", "xp_earned", "timestamp"}
        row = AssessmentResult(
            id=result.get("id") or f"{result['session_id']}_{result.get('timestamp', '')}",
            student_id=result["student_id"],
            session_id=result.get("session_id"),
            score=result.get("score", result.get("percentage")),
            percentage=result.get("percentage"),
            xp_earned=result.get("xp_earned", 0),
            timestamp=result.get("timestamp", datetime.utcnow().timestamp()),
            payload={k: v for k, v in result.items() if k not in known},
        )
        db.add(row)
        session = db.get(AssessmentSession, result.get("session_id"))
        if session:
            session.completion_status = result.get("completion_status", "completed")
            session.completed_at = datetime.utcfromtimestamp(result["timestamp"]) if result.get("timestamp") else datetime.utcnow()
            session.ending_difficulty = result.get("next_difficulty")
            session.total_score = result.get("earned_points")
            session.percentage = result.get("percentage")
            session.total_duration_seconds = result.get("time_spent")
            session.number_of_questions = result.get("total_questions")
            session.number_correct = result.get("correct_answers")
        db.commit()
    finally:
        db.close()


def get_student_results(student_id: str) -> list[dict]:
    db = _session()
    try:
        rows = db.execute(
            select(AssessmentResult).where(AssessmentResult.student_id == student_id)
        ).scalars().all()
        out = []
        for r in rows:
            d = dict(r.payload or {})
            d.update({
                "student_id": r.student_id, "session_id": r.session_id,
                "score": r.score, "percentage": r.percentage,
                "xp_earned": r.xp_earned, "timestamp": r.timestamp,
            })
            out.append(d)
        return out
    finally:
        db.close()


def get_recent_scores_pct(student_id: str, limit: int = 5) -> list[float]:
    db = _session()
    try:
        rows = db.execute(
            select(AssessmentResult.percentage, AssessmentResult.timestamp)
            .where(AssessmentResult.student_id == student_id)
            .order_by(AssessmentResult.timestamp.asc())
        ).all()
        return [r[0] for r in rows[-limit:] if r[0] is not None]
    finally:
        db.close()


# ── CRS history (unchanged shape from legacy — Phase 10/11) ────

def save_crs_record(record: dict) -> dict:
    required = {
        "student_id", "timestamp", "performance", "behavioral_cue", "integrity",
        "trend", "complexity", "crs", "difficulty", "explanation",
    }
    missing = required - record.keys()
    if missing:
        raise ValueError(f"save_crs_record missing required fields: {sorted(missing)}")

    record = dict(record)
    record.setdefault("assessment_id", None)
    db = _session()
    try:
        row = CRSHistory(**{k: record[k] for k in [
            "student_id", "assessment_id", "timestamp", "performance",
            "behavioral_cue", "integrity", "trend", "complexity", "crs",
            "difficulty", "explanation",
        ]})
        row.study_session_id = record.get("study_session_id")
        row.participant_id = record.get("participant_id")
        row.condition = record.get("condition")
        db.add(row)
        db.commit()
        logger.info(
            f"CRS persisted: student={record['student_id']} crs={record['crs']:.3f} "
            f"difficulty={record['difficulty']}"
        )
    finally:
        db.close()
    return record


def get_crs_history(student_id: str, limit: Optional[int] = None) -> list[dict]:
    db = _session()
    try:
        rows = db.execute(
            select(CRSHistory)
            .where(CRSHistory.student_id == student_id)
            .order_by(CRSHistory.timestamp.asc())
        ).scalars().all()
        records = [{
            "student_id": r.student_id, "assessment_id": r.assessment_id,
            "timestamp": r.timestamp, "performance": r.performance,
            "behavioral_cue": r.behavioral_cue, "integrity": r.integrity, "trend": r.trend,
            "complexity": r.complexity, "crs": r.crs, "difficulty": r.difficulty,
            "explanation": r.explanation,
        } for r in rows]
        return records[-limit:] if limit else records
    finally:
        db.close()


def get_current_crs(student_id: str) -> Optional[dict]:
    history = get_crs_history(student_id)
    return history[-1] if history else None


def _parse_dt(value) -> Optional[datetime]:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def save_generated_questions(session: dict) -> None:
    db = _session()
    try:
        for q in session.get("questions", []):
            meta = q.get("llm_metadata") or {}
            row = GeneratedQuestion(
                question_id=q["id"],
                study_session_id=session.get("study_session_id"),
                assessment_session_id=session.get("id"),
                model_version=meta.get("model"),
                generated_live_fallback=meta.get("generated_from"),
                source_material=", ".join(session.get("contributing_video_ids") or []) or session.get("video_id") or session.get("course_id"),
                difficulty=q.get("difficulty"),
                bloom_level=meta.get("blooms_level"),
                generation_timestamp=datetime.utcnow(),
                question_metadata=meta,
            )
            db.merge(row)
        db.commit()
    finally:
        db.close()


def save_question_responses(
    *,
    study_session: dict,
    assessment_session: dict,
    answers: dict,
    response_events: Optional[list[dict]],
    submitted_at: datetime,
    total_time_spent: float,
    decision_method: Optional[str] = None,
) -> list[dict]:
    questions = assessment_session.get("questions", [])
    events = {e.get("question_id"): e for e in (response_events or []) if e.get("question_id")}
    fallback_per_question = total_time_spent / max(len(questions), 1)
    rows_out = []
    db = _session()
    try:
        for idx, q in enumerate(questions):
            question_id = q["id"]
            event = events.get(question_id, {})
            try:
                idx = int(event.get("question_index", idx))
            except (TypeError, ValueError):
                pass
            existing = db.execute(
                select(QuestionResponse).where(
                    QuestionResponse.study_session_id == study_session["study_session_id"],
                    QuestionResponse.assessment_session_id == assessment_session["id"],
                    QuestionResponse.question_id == question_id,
                )
            ).scalar_one_or_none()
            submitted_answer = answers.get(question_id)
            status = event.get("status")
            if status is None:
                status = "submitted" if submitted_answer is not None else "unanswered"
            presented = _parse_dt(event.get("presented_at"))
            submitted = _parse_dt(event.get("submitted_at")) or (submitted_at if submitted_answer is not None else None)
            response_time = event.get("response_time_seconds")
            if response_time is None:
                response_time = fallback_per_question if submitted_answer is not None else None
            try:
                response_time = None if response_time is None else max(0.0, float(response_time))
            except (TypeError, ValueError):
                response_time = None
            correct = None
            points = 0.0
            if submitted_answer is not None:
                correct = submitted_answer == q.get("correct_answer")
                points = float(q.get("points", 10) if correct else 0)
            meta = q.get("llm_metadata") or {}
            if existing is None:
                existing = QuestionResponse(
                    study_session_id=study_session["study_session_id"],
                    assessment_session_id=assessment_session["id"],
                    participant_id=study_session["participant_id"],
                    condition=study_session["condition"],
                    question_id=question_id,
                    question_index=idx,
                )
                db.add(existing)
            method = decision_method or q.get("adaptive_method") or study_session.get("condition")
            if method not in {"MCRF", "LEGACY"}:
                method = None
            existing.condition = method or existing.condition
            existing.question_difficulty = q.get("difficulty")
            existing.question_source = meta.get("generated_from")
            existing.model_provider = meta.get("model")
            existing.live_fallback_status = meta.get("generated_from")
            existing.bloom_level = meta.get("blooms_level")
            existing.presented_at = presented
            existing.submitted_at = submitted
            existing.response_time_seconds = response_time
            existing.submitted_answer = None if submitted_answer is None else str(submitted_answer)
            existing.correctness = correct
            existing.score_points = points
            existing.status = status
            rows_out.append({
                "question_id": question_id,
                "question_index": idx,
                "condition": method,
                "response_time_seconds": response_time,
                "correctness": correct,
                "status": status,
            })
        db.commit()
    finally:
        db.close()
    return rows_out


def save_single_question_response(
    *,
    study_session: dict,
    assessment_session: dict,
    question: dict,
    question_index: int,
    answer,
    response_event: Optional[dict],
    submitted_at: datetime,
    decision_method: Optional[str] = None,
) -> dict:
    event = dict(response_event or {})
    event.setdefault("question_id", question["id"])
    event.setdefault("question_index", question_index)
    rows = save_question_responses(
        study_session=study_session,
        assessment_session={**assessment_session, "questions": [question]},
        answers={question["id"]: answer},
        response_events=[event],
        submitted_at=submitted_at,
        total_time_spent=float(event.get("response_time_seconds") or 0),
        decision_method=decision_method,
    )
    return rows[0]


def update_assessment_adaptive_state(
    session_id: str,
    *,
    questions: Optional[list[dict]] = None,
    selected_difficulty: Optional[str] = None,
    adaptive_state: Optional[dict] = None,
    completion_status: Optional[str] = None,
) -> Optional[dict]:
    db = _session()
    try:
        row = db.get(AssessmentSession, session_id)
        if not row:
            return None
        if questions is not None:
            row.questions = questions
            row.number_of_questions = len(questions)
        if selected_difficulty is not None:
            row.selected_difficulty = selected_difficulty
        if adaptive_state is not None:
            row.adaptive_state = adaptive_state
        if completion_status is not None:
            row.completion_status = completion_status
        db.commit()
        db.refresh(row)
        return {
            "id": row.id, "student_id": row.student_id, "questions": row.questions or [],
            "study_session_id": row.study_session_id,
            "participant_id": row.participant_id,
            "condition": row.condition,
            "course_id": row.course_id,
            "video_id": row.video_id,
            "contributing_video_ids": row.contributing_video_ids or [],
            "difficulty": row.difficulty, "time_limit": row.time_limit,
            "starting_difficulty": row.starting_difficulty or row.difficulty,
            "selected_difficulty": row.selected_difficulty or row.difficulty,
            "completion_status": row.completion_status,
            "attention_score_during_video": row.attention_score_during_video,
            "transcript_text": row.transcript_text,
            "adaptive_state": row.adaptive_state or {},
            "adaptive_metadata": (row.adaptive_state or {}).get("adaptive_metadata", {
                "previous_score": None,
                "adjusted_difficulty": row.difficulty,
                "reason": "Assessment protocol initialized.",
            }),
        }
    finally:
        db.close()


def save_research_crs_decision(
    *,
    study_session: dict,
    assessment_session: dict,
    adaptive_result: dict,
    previous_scores: list[float],
    per_question_responses: list[dict],
    previous_difficulty: str,
    attention_score: float,
    transcript_text: Optional[str],
    decision_index: Optional[int] = None,
    method: str = "MCRF",
) -> Optional[dict]:
    crs_block = adaptive_result.get("crs")
    if not crs_block or method != "MCRF":
        return None
    db = _session()
    try:
        existing_stmt = select(ResearchCRSDecision).where(
            ResearchCRSDecision.study_session_id == study_session["study_session_id"],
            ResearchCRSDecision.assessment_session_id == assessment_session["id"],
        )
        if decision_index is not None:
            existing_stmt = existing_stmt.where(ResearchCRSDecision.decision_index == decision_index)
        existing = db.execute(existing_stmt).scalar_one_or_none()
        if existing:
            return {
                "id": existing.id,
                "decision_index": existing.decision_index,
                "crs": existing.crs,
            }
        prior_count = db.execute(
            select(func.count(ResearchCRSDecision.id)).where(
                ResearchCRSDecision.study_session_id == study_session["study_session_id"]
            )
        ).scalar_one()
        decision_index = int(decision_index or int(prior_count or 0) + 1)
        weights = crs_block.get("weights_used", {})
        components = crs_block.get("components", {})
        timing_values = [
            r.get("response_time_seconds")
            for r in per_question_responses
            if r.get("response_time_seconds") is not None
        ]
        row = ResearchCRSDecision(
            study_session_id=study_session["study_session_id"],
            assessment_session_id=assessment_session["id"],
            participant_id=study_session["participant_id"],
            condition=method,
            decision_index=decision_index,
            timestamp=datetime.utcnow(),
            performance=components["performance"],
            behavioral_cue=components["behavioral_cue"],
            response_timing=components["integrity"],
            trend=components["trend"],
            complexity=components["complexity"],
            crs=crs_block["score"],
            alpha=weights["alpha"],
            beta=weights["beta"],
            gamma=weights["gamma"],
            delta=weights["delta"],
            epsilon=weights["epsilon"],
            selected_difficulty=adaptive_result["next_assessment_difficulty"],
            previous_difficulty=previous_difficulty,
            explanation=crs_block.get("explanation"),
            performance_inputs={"recent_scores_pct": previous_scores},
            timing_inputs={"response_times_seconds": timing_values},
            trend_inputs={"recent_scores_pct": previous_scores},
            complexity_inputs={
                "source_material": assessment_session.get("video_id") or assessment_session.get("course_id"),
                "transcript_present": bool(transcript_text and transcript_text.strip()),
                "transcript_length": len(transcript_text or ""),
            },
            detail=crs_block.get("detail") or {},
        )
        db.add(row)
        db.commit()
        return {"id": row.id, "decision_index": decision_index, "crs": row.crs}
    finally:
        db.close()


def save_research_legacy_decision(
    *,
    study_session: dict,
    assessment_session: dict,
    adaptive_result: dict,
    previous_scores: list[float],
    per_question_responses: list[dict],
    previous_difficulty: str,
    current_score: float,
    decision_index: Optional[int] = None,
    method: str = "LEGACY",
) -> Optional[dict]:
    if method != "LEGACY":
        return None
    db = _session()
    try:
        existing_stmt = select(ResearchLegacyDecision).where(
            ResearchLegacyDecision.study_session_id == study_session["study_session_id"],
            ResearchLegacyDecision.assessment_session_id == assessment_session["id"],
        )
        if decision_index is not None:
            existing_stmt = existing_stmt.where(ResearchLegacyDecision.decision_index == decision_index)
        existing = db.execute(existing_stmt).scalar_one_or_none()
        if existing:
            return {"id": existing.id, "decision_index": existing.decision_index}
        prior_count = db.execute(
            select(func.count(ResearchLegacyDecision.id)).where(
                ResearchLegacyDecision.study_session_id == study_session["study_session_id"]
            )
        ).scalar_one()
        decision_index = int(decision_index or int(prior_count or 0) + 1)
        row = ResearchLegacyDecision(
            study_session_id=study_session["study_session_id"],
            assessment_session_id=assessment_session["id"],
            participant_id=study_session["participant_id"],
            condition=method,
            decision_index=decision_index,
            timestamp=datetime.utcnow(),
            performance_input=current_score,
            performance_history=previous_scores,
            previous_difficulty=previous_difficulty,
            selected_difficulty=adaptive_result["next_assessment_difficulty"],
            explanation=adaptive_result.get("recommended_action"),
            detail={
                "performance_trend": adaptive_result.get("performance_trend"),
                "strength_areas": adaptive_result.get("strength_areas", []),
                "weak_areas": adaptive_result.get("weak_areas", []),
                "question_responses": per_question_responses,
            },
        )
        db.add(row)
        db.commit()
        return {"id": row.id, "decision_index": decision_index}
    finally:
        db.close()


def refresh_behavioral_summary(study_session_id: str) -> Optional[dict]:
    db = _session()
    try:
        study = db.get(StudySession, study_session_id)
        if not study:
            return None
        logs = db.execute(
            select(AttentionLog).where(AttentionLog.study_session_id == study_session_id)
        ).scalars().all()
        scores = [float(l.score) / 100.0 for l in logs if l.score is not None]
        state_counts: dict[str, int] = {}
        for log in logs:
            state_counts[log.state or "unknown"] = state_counts.get(log.state or "unknown", 0) + 1
        total = max(len(logs), 1)
        proportions = {k: v / total for k, v in state_counts.items()}
        existing = db.execute(
            select(BehavioralSummary).where(BehavioralSummary.study_session_id == study_session_id)
        ).scalar_one_or_none()
        if existing is None:
            existing = BehavioralSummary(
                study_session_id=study_session_id,
                participant_id=study.participant_id,
                condition=study.condition,
            )
            db.add(existing)
        existing.mean_b = statistics.mean(scores) if scores else 0.5
        existing.median_b = statistics.median(scores) if scores else 0.5
        existing.stddev_b = statistics.pstdev(scores) if len(scores) > 1 else 0.0
        existing.min_b = min(scores) if scores else 0.5
        existing.max_b = max(scores) if scores else 0.5
        existing.observation_count = len(scores)
        existing.behavioral_state_proportions = proportions
        existing.camera_used = study.camera_used
        existing.camera_opted_out = study.camera_opted_out
        existing.camera_revoked = study.camera_revoked
        existing.updated_at = datetime.utcnow()
        db.commit()
        return {"study_session_id": study_session_id, "observation_count": existing.observation_count}
    finally:
        db.close()


def save_prepost_results(study_session_id: str, test_type: str, responses: list[dict]) -> dict:
    test_type = test_type.lower()
    if test_type not in {"pre", "post"}:
        raise ValueError("test_type must be 'pre' or 'post'")
    db = _session()
    try:
        study = db.get(StudySession, study_session_id)
        if not study:
            raise ValueError("Study session not found")
        scores = []
        for idx, r in enumerate(responses):
            row = db.execute(
                select(PrePostResult).where(
                    PrePostResult.study_session_id == study_session_id,
                    PrePostResult.test_type == test_type,
                    PrePostResult.question_id == r["question_id"],
                )
            ).scalar_one_or_none()
            if row is None:
                row = PrePostResult(
                    study_session_id=study_session_id,
                    participant_id=study.participant_id,
                    test_type=test_type,
                    question_id=r["question_id"],
                )
                db.add(row)
            row.question_index = int(r.get("question_index", idx))
            row.correctness = r.get("correctness")
            row.response_time_seconds = r.get("response_time_seconds")
            row.score = r.get("score")
            row.started_at = _parse_dt(r.get("started_at"))
            row.completed_at = _parse_dt(r.get("completed_at"))
            if r.get("score") is not None:
                scores.append(float(r["score"]))
        total_score = sum(scores) if scores else None
        if test_type == "pre":
            study.pretest_score = total_score
        else:
            study.posttest_score = total_score
        if study.pretest_score is not None and study.posttest_score is not None:
            study.learning_gain = study.posttest_score - study.pretest_score
        db.commit()
        return {
            "study_session_id": study_session_id,
            "test_type": test_type,
            "score": total_score,
            "learning_gain": study.learning_gain,
        }
    finally:
        db.close()


def _component_history(student_id: str, component: str, limit: Optional[int]) -> list[dict]:
    records = get_crs_history(student_id, limit=limit)
    return [
        {"timestamp": r["timestamp"], "assessment_id": r.get("assessment_id"), "value": r[component]}
        for r in records
    ]


def get_performance_history(student_id: str, limit: Optional[int] = None) -> list[dict]:
    return _component_history(student_id, "performance", limit)


def get_behavioral_cue_history(student_id: str, limit: Optional[int] = None) -> list[dict]:
    return _component_history(student_id, "behavioral_cue", limit)


def get_integrity_history(student_id: str, limit: Optional[int] = None) -> list[dict]:
    return _component_history(student_id, "integrity", limit)


def get_trend_history(student_id: str, limit: Optional[int] = None) -> list[dict]:
    return _component_history(student_id, "trend", limit)


def get_complexity_history(student_id: str, limit: Optional[int] = None) -> list[dict]:
    return _component_history(student_id, "complexity", limit)


# ── Consent (CR6 fix, now Postgres-backed) ──────────────────

def get_consent(student_id: str, session_id: Optional[str] = None) -> Optional[dict]:
    db = _session()
    try:
        if session_id is None:
            c = db.execute(
                select(Consent)
                .where(Consent.student_id == student_id)
                .order_by(Consent.granted_at.desc())
                .limit(1)
            ).scalar_one_or_none()
        else:
            c = db.get(Consent, {"student_id": student_id, "session_id": session_id})
        if not c:
            return None
        return {
            "student_id": c.student_id, "session_id": c.session_id, "granted": c.granted,
            "granted_at": c.granted_at.isoformat() if c.granted_at else None,
            "retention_days": c.retention_days,
            "raw_frames_stored": c.raw_frames_stored, "version": c.version,
        }
    finally:
        db.close()


def set_consent(record: dict) -> dict:
    db = _session()
    try:
        granted_at = record.get("granted_at")
        if isinstance(granted_at, str):
            granted_at = datetime.fromisoformat(granted_at.replace("Z", "+00:00"))
        row = Consent(
            student_id=record["student_id"],
            session_id=record["session_id"],
            study_session_id=record.get("study_session_id"),
            granted=record["granted"],
            granted_at=granted_at or datetime.utcnow(),
            retention_days=record.get("retention_days", 30),
            raw_frames_stored=record.get("raw_frames_stored", False),
            version=record.get("version", "1.0"),
        )
        db.merge(row)
        if record.get("study_session_id"):
            study = db.get(StudySession, record["study_session_id"])
            if study:
                if record["granted"]:
                    study.camera_used = True
                else:
                    if study.camera_used:
                        study.camera_revoked = True
                    else:
                        study.camera_opted_out = True
        db.commit()
    finally:
        db.close()
    return record


def purge_expired_attention_logs() -> int:
    """Delete attention_logs rows older than the retention window the
    student consented to (default 30 days)."""
    from datetime import timedelta
    db = _session()
    removed = 0
    try:
        consents = db.execute(select(Consent)).scalars().all()
        for c in consents:
            cutoff = (datetime.utcnow() - timedelta(days=c.retention_days)).isoformat()
            stale = db.execute(
                select(AttentionLog).where(
                    AttentionLog.student_id == c.student_id,
                    AttentionLog.timestamp < cutoff,
                )
            ).scalars().all()
            for row in stale:
                db.delete(row)
                removed += 1
        db.commit()
    finally:
        db.close()
    return removed


def log_attention(log: dict):
    db = _session()
    try:
        participant_id = log.get("participant_id")
        if not participant_id and log.get("study_session_id"):
            study = db.get(StudySession, log["study_session_id"])
            participant_id = study.participant_id if study else None
        row = AttentionLog(
            student_id=log["student_id"], participant_id=participant_id,
            study_session_id=log.get("study_session_id"), session_id=log.get("session_id"),
            video_id=log.get("video_id"),
            timestamp=log.get("timestamp"), score=log.get("score"),
            state=log.get("state"), confidence=log.get("confidence"),
            message=log.get("message"), model_response=log.get("model_response", {}),
            source=log.get("source", "dummy"),
            consent_confirmed=log.get("consent_confirmed", False),
        )
        db.add(row)
        if log.get("study_session_id"):
            study = db.get(StudySession, log["study_session_id"])
            if study:
                study.camera_used = True
        db.commit()
    finally:
        db.close()


def get_attention_logs(video_id: str, student_id: str) -> list[dict]:
    db = _session()
    try:
        rows = db.execute(
            select(AttentionLog).where(
                AttentionLog.video_id == video_id, AttentionLog.student_id == student_id
            )
        ).scalars().all()
        return [{
            "student_id": r.student_id, "video_id": r.video_id, "timestamp": r.timestamp,
            "participant_id": r.participant_id,
            "study_session_id": r.study_session_id,
            "session_id": r.session_id,
            "score": r.score, "state": r.state, "confidence": r.confidence,
            "message": r.message, "model_response": r.model_response,
            "source": r.source, "consent_confirmed": r.consent_confirmed,
        } for r in rows]
    finally:
        db.close()


# ── Leaderboard — now a REAL live query, not a static seeded table ────
# FIX (this request): previously `leaderboard_table` was a hand-seeded
# TinyDB table of fictional students (Priya Sharma, Marcus Chen, ...)
# that never changed no matter what any real student did. It is gone —
# the leaderboard below is computed by ordering the real `users` table.

def get_leaderboard(limit: int = 50) -> list[dict]:
    db = _session()
    try:
        rows = db.execute(
            select(User).order_by(User.xp.desc()).limit(limit)
        ).scalars().all()
        return [
            {
                "rank": i + 1,
                "student_id": u.id,
                "name": u.name,
                "avatar": u.avatar or "",
                "xp": u.xp,
                "level": u.level,
                "streak": u.streak,
                "courses_completed": u.total_courses_completed,
            }
            for i, u in enumerate(rows)
        ]
    finally:
        db.close()


# ── Daily challenges — now per-student (FIX, remaining-things request) ──
# Previously get_daily_challenges() returned one global row per
# challenge with a shared `completed`/`progress` — one student finishing
# a challenge marked it finished for everyone. Progress now lives in
# DailyChallengeProgress, scoped to (student_id, challenge_id, today).

def _get_or_create_progress(db: Session, student_id: str, challenge_id: str) -> DailyChallengeProgress:
    today = date.today()
    row = db.execute(
        select(DailyChallengeProgress).where(
            DailyChallengeProgress.student_id == student_id,
            DailyChallengeProgress.challenge_id == challenge_id,
            DailyChallengeProgress.challenge_date == today,
        )
    ).scalar_one_or_none()
    if row is None:
        row = DailyChallengeProgress(
            student_id=student_id, challenge_id=challenge_id, challenge_date=today,
            progress=0, completed=False, xp_awarded=False,
        )
        db.add(row)
        db.flush()
    return row


def get_daily_challenges(student_id: str) -> list[dict]:
    db = _session()
    try:
        templates = db.execute(select(DailyChallenge)).scalars().all()
        out = []
        for t in templates:
            progress_row = _get_or_create_progress(db, student_id, t.id)
            out.append({
                "id": t.id, "title": t.title, "description": t.description,
                "xp_reward": t.xp_reward, "type": t.type, "target": t.target,
                "progress": progress_row.progress, "completed": progress_row.completed,
            })
        db.commit()
        return out
    finally:
        db.close()


def advance_challenge_progress(student_id: str, challenge_type: str, amount: int = 1, set_to: Optional[int] = None) -> list[dict]:
    """
    Bump progress on every challenge of `challenge_type` for this student
    today (usually just one, but supports several sharing a type). Caps
    at the challenge's target and marks completed exactly once; awards
    XP exactly once per (student, challenge, day) via `xp_awarded`, so
    calling this multiple times in one day is always safe/idempotent.
    Returns the list of challenges that just newly completed (empty if
    none did) so the caller can surface a "+XP" toast.
    """
    db = _session()
    newly_completed = []
    try:
        templates = db.execute(
            select(DailyChallenge).where(DailyChallenge.type == challenge_type)
        ).scalars().all()
        for t in templates:
            row = _get_or_create_progress(db, student_id, t.id)
            if row.completed:
                continue
            row.progress = set_to if set_to is not None else min(row.progress + amount, t.target)
            if row.progress >= t.target:
                row.completed = True
                row.completed_at = datetime.utcnow()
                if not row.xp_awarded:
                    user = db.get(User, student_id)
                    if user:
                        apply_xp(user, t.xp_reward)
                    row.xp_awarded = True
                    newly_completed.append({"id": t.id, "title": t.title, "xp_reward": t.xp_reward})
        db.commit()
    finally:
        db.close()
    return newly_completed


def record_daily_activity(student_id: str) -> dict:
    """
    FIX (remaining-things request): `streak`/`best_streak` existed as
    User columns but nothing ever updated them. Called from the login
    endpoint (and could be called from any "the student did something
    today" event): if last_active_date was yesterday, streak += 1; if it
    was already today, no change (idempotent — logging in twice in a day
    doesn't inflate the streak); if it was any earlier date (or never),
    the streak resets to 1. best_streak tracks the historical max.
    Also advances the "Streak Keeper" daily challenge for today.
    """
    db = _session()
    try:
        user = db.get(User, student_id)
        if not user:
            return {}
        today = date.today()
        if user.last_active_date == today:
            pass  # already recorded today — no-op, not a double-count
        elif user.last_active_date == today - timedelta(days=1):
            user.streak += 1
        else:
            user.streak = 1
        user.best_streak = max(user.best_streak, user.streak)
        user.last_active_date = today
        db.commit()
        streak_result = {"streak": user.streak, "best_streak": user.best_streak}
    finally:
        db.close()
    advance_challenge_progress(student_id, "streak", set_to=1)
    return streak_result


def get_notifications(student_id: str = "student_001") -> list[dict]:
    db = _session()
    try:
        rows = db.execute(select(Notification)).scalars().all()
        return [{
            "id": n.id, "type": n.type, "title": n.title, "message": n.message,
            "timestamp": n.timestamp, "read": n.read, "icon": n.icon,
        } for n in rows]
    finally:
        db.close()


# ── Auto Courses ─────────────────────────────────────────────

def save_auto_course(course_data: dict) -> None:
    db = _session()
    try:
        row = AutoCourse(
            course_id=course_data["course_id"],
            course_title=course_data.get("course_title"),
            description=course_data.get("description"),
            icon=course_data.get("icon"),
            category=course_data.get("category"),
            difficulty=course_data.get("difficulty"),
            tags=course_data.get("tags", []),
            videos=course_data.get("videos", []),
            generated_at=course_data.get("generated_at", 0),
        )
        db.merge(row)
        db.commit()
    finally:
        db.close()


def get_auto_course(course_id: str) -> Optional[dict]:
    db = _session()
    try:
        c = db.get(AutoCourse, course_id)
        if not c:
            return None
        return {
            "course_id": c.course_id, "course_title": c.course_title,
            "description": c.description, "icon": c.icon, "category": c.category,
            "difficulty": c.difficulty, "tags": c.tags or [], "videos": c.videos or [],
            "generated_at": c.generated_at,
        }
    finally:
        db.close()


def get_all_auto_courses() -> list[dict]:
    db = _session()
    try:
        rows = db.execute(select(AutoCourse)).scalars().all()
        courses = [{
            "course_id": c.course_id, "course_title": c.course_title,
            "description": c.description, "icon": c.icon, "category": c.category,
            "difficulty": c.difficulty, "tags": c.tags or [], "videos": c.videos or [],
            "generated_at": c.generated_at,
        } for c in rows]
        return sorted(courses, key=lambda c: c.get("generated_at", 0), reverse=True)
    finally:
        db.close()


def update_video_transcription_status(course_id: str, video_id: str, available: bool) -> None:
    db = _session()
    try:
        c = db.get(AutoCourse, course_id)
        if not c:
            return
        videos = c.videos or []
        for v in videos:
            if v.get("id") == video_id:
                v["transcription_available"] = available
        c.videos = videos
        db.commit()
    finally:
        db.close()


def save_auto_course_to_courses(course_id: str) -> Optional[dict]:
    auto_course = get_auto_course(course_id)
    if not auto_course:
        return None

    def _to_title_case_difficulty(value: str) -> str:
        normalized = (value or "Intermediate").strip().lower()
        mapping = {"beginner": "Beginner", "intermediate": "Intermediate", "advanced": "Advanced"}
        return mapping.get(normalized, "Intermediate")

    videos = auto_course.get("videos", [])
    converted_videos = []
    for idx, video in enumerate(videos, start=1):
        converted_videos.append({
            "id": video.get("id", f"auto_v_{idx}"),
            "title": video.get("title", f"Video {idx}"),
            "url": video.get("url", ""),
            "duration": int(video.get("duration", 0) or 0),
            "thumbnail": video.get("thumbnail", ""),
            "order": int(video.get("order", idx)),
            "completed": bool(video.get("completed", False)),
            "watched_percent": float(video.get("watched_percent", 0.0) or 0.0),
            # FIX (course generator request): was silently dropped here —
            # same class of bug as an undeclared response_model field.
            "stage_label": video.get("stage_label", ""),
        })

    total_videos = len(converted_videos)
    completed_videos = sum(1 for v in converted_videos if v.get("completed"))
    total_seconds = sum(int(v.get("duration", 0) or 0) for v in converted_videos)
    estimated_hours = round(total_seconds / 3600, 1) if total_seconds > 0 else round(max(total_videos, 1) * 0.2, 1)
    progress = round((completed_videos / total_videos) * 100, 1) if total_videos > 0 else 0.0

    course_doc = {
        "id": auto_course.get("course_id", course_id),
        "title": auto_course.get("course_title", "Auto Course"),
        "description": auto_course.get("description", "Auto-generated course"),
        "icon": auto_course.get("icon", "🎓"),
        "category": auto_course.get("category", "Auto-Generated"),
        "difficulty": _to_title_case_difficulty(auto_course.get("difficulty", "Intermediate")),
        "total_videos": total_videos,
        "completed_videos": completed_videos,
        "progress": progress,
        "estimated_hours": max(0.1, estimated_hours),
        "tags": auto_course.get("tags", ["auto-generated"]),
        "video_links": converted_videos,
    }

    db = _session()
    try:
        row = Course(**course_doc)
        db.merge(row)
        db.commit()
    finally:
        db.close()

    return course_doc


# ── Refresh tokens (remaining-things request) ────────────────
# FIX: access tokens previously had no revocation mechanism — logging
# out only meant "the browser forgot the token", nothing server-side
# actually invalidated it. Refresh tokens are stored as a SHA-256 hash
# (never the raw value) and can be revoked for real.

def create_refresh_token(student_id: str, token_hash: str, expires_at: datetime) -> None:
    db = _session()
    try:
        db.add(RefreshToken(user_id=student_id, token_hash=token_hash, expires_at=expires_at))
        db.commit()
    finally:
        db.close()


def get_valid_refresh_token(token_hash: str) -> Optional[dict]:
    db = _session()
    try:
        row = db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        ).scalar_one_or_none()
        if row is None or row.revoked or row.expires_at < datetime.utcnow():
            return None
        return {"id": row.id, "user_id": row.user_id, "expires_at": row.expires_at}
    finally:
        db.close()


def revoke_refresh_token(token_hash: str) -> None:
    db = _session()
    try:
        row = db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        ).scalar_one_or_none()
        if row:
            row.revoked = True
            db.commit()
    finally:
        db.close()


def revoke_all_refresh_tokens(student_id: str) -> int:
    """Used by 'log out everywhere' / password reset (rotating the
    password should kill every existing session, not just the current
    device's)."""
    db = _session()
    try:
        rows = db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == student_id, RefreshToken.revoked == False  # noqa: E712
            )
        ).scalars().all()
        for row in rows:
            row.revoked = True
        db.commit()
        return len(rows)
    finally:
        db.close()


# ── Password reset (remaining-things request) ────────────────
# FIX: there was no password reset flow at all before this.

def create_password_reset_token(student_id: str, token_hash: str, expires_at: datetime) -> None:
    db = _session()
    try:
        # Invalidate any earlier unused reset tokens for this user first
        # — only the most recently requested link should ever work.
        old = db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == student_id, PasswordResetToken.used == False  # noqa: E712
            )
        ).scalars().all()
        for row in old:
            row.used = True
        db.add(PasswordResetToken(user_id=student_id, token_hash=token_hash, expires_at=expires_at))
        db.commit()
    finally:
        db.close()


def get_valid_password_reset_token(token_hash: str) -> Optional[dict]:
    db = _session()
    try:
        row = db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        ).scalar_one_or_none()
        if row is None or row.used or row.expires_at < datetime.utcnow():
            return None
        return {"id": row.id, "user_id": row.user_id}
    finally:
        db.close()


def mark_password_reset_token_used(token_hash: str) -> None:
    db = _session()
    try:
        row = db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        ).scalar_one_or_none()
        if row:
            row.used = True
            db.commit()
    finally:
        db.close()


def set_user_password(student_id: str, new_hashed_password: str) -> None:
    db = _session()
    try:
        user = db.get(User, student_id)
        if user:
            user.hashed_password = new_hashed_password
            db.commit()
    finally:
        db.close()


# ── Seeding ──────────────────────────────────────────────────
# Global demo content (courses, daily challenges, notifications) is
# seeded so the app isn't empty on first run. Student accounts are NOT
# seeded here — they're created for real via POST /api/auth/signup (see
# scripts/seed_demo_accounts.py for a script that does exactly that, so
# the leaderboard has real, auth-created rows to show on a fresh demo).

def seed_database():
    db = _session()
    try:
        if db.execute(select(Course).limit(1)).first() is None:
            _seed_courses(db)
        if db.execute(select(DailyChallenge).limit(1)).first() is None:
            _seed_challenges(db)
        if db.execute(select(Notification).limit(1)).first() is None:
            _seed_notifications(db)
        db.commit()
        logger.success("Postgres seed check complete (courses/challenges/notifications)")
    finally:
        db.close()


def _seed_courses(db: Session):
    courses = [
        {
            "id": "course_001", "title": "Introduction to React",
            "description": "Master the fundamentals of React including components, props, state, and hooks",
            "icon": "⚛️", "category": "Frontend", "difficulty": "Beginner",
            "total_videos": 8, "completed_videos": 5, "progress": 65, "estimated_hours": 6,
            "tags": ["React", "JavaScript", "Frontend"],
            "video_links": [
                {"id": "v1", "title": "What is React? — Introduction & Setup", "url": "https://www.youtube.com/watch?v=SqcY0GlETPk", "duration": 720, "thumbnail": "", "order": 1, "completed": True, "watched_percent": 100},
                {"id": "v2", "title": "JSX & Components Deep Dive", "url": "https://www.youtube.com/watch?v=9YkUCRr3bVc", "duration": 890, "thumbnail": "", "order": 2, "completed": True, "watched_percent": 100},
                {"id": "v3", "title": "Props & Data Flow", "url": "https://www.youtube.com/watch?v=PHaECbrKgs0", "duration": 650, "thumbnail": "", "order": 3, "completed": True, "watched_percent": 100},
                {"id": "v4", "title": "State & useState Hook", "url": "https://www.youtube.com/watch?v=O6P86uwfdR0", "duration": 780, "thumbnail": "", "order": 4, "completed": True, "watched_percent": 100},
                {"id": "v5", "title": "useEffect & Side Effects", "url": "https://www.youtube.com/watch?v=0ZJgIjIuY7U", "duration": 920, "thumbnail": "", "order": 5, "completed": True, "watched_percent": 100},
                {"id": "v6", "title": "Event Handling & Forms", "url": "https://www.youtube.com/watch?v=dH6i3GurZW8", "duration": 640, "thumbnail": "", "order": 6, "completed": False, "watched_percent": 35},
                {"id": "v7", "title": "Conditional Rendering", "url": "https://www.youtube.com/watch?v=4oCVDkb_peY", "duration": 540, "thumbnail": "", "order": 7, "completed": False, "watched_percent": 0},
                {"id": "v8", "title": "Lists & Keys", "url": "https://www.youtube.com/watch?v=0sasRxl35_8", "duration": 480, "thumbnail": "", "order": 8, "completed": False, "watched_percent": 0},
            ],
        },
        {
            "id": "course_002", "title": "Advanced State Management",
            "description": "Redux, Context API, Zustand and modern state patterns",
            "icon": "🔄", "category": "Frontend", "difficulty": "Intermediate",
            "total_videos": 6, "completed_videos": 2, "progress": 42, "estimated_hours": 8,
            "tags": ["Redux", "Context API", "Zustand"],
            "video_links": [
                {"id": "v9", "title": "Why State Management Matters", "url": "https://www.youtube.com/watch?v=CVpUuw9XSjY", "duration": 600, "thumbnail": "", "order": 1, "completed": True, "watched_percent": 100},
                {"id": "v10", "title": "Context API Fundamentals", "url": "https://www.youtube.com/watch?v=5LrDIWkK_Bc", "duration": 750, "thumbnail": "", "order": 2, "completed": True, "watched_percent": 100},
                {"id": "v11", "title": "Redux Toolkit Setup", "url": "https://www.youtube.com/watch?v=9zySeP5vH9c", "duration": 880, "thumbnail": "", "order": 3, "completed": False, "watched_percent": 20},
                {"id": "v12", "title": "Redux Thunk & Async", "url": "https://www.youtube.com/watch?v=93p3LxR9xfM", "duration": 920, "thumbnail": "", "order": 4, "completed": False, "watched_percent": 0},
                {"id": "v13", "title": "Zustand — Lightweight Alternative", "url": "https://www.youtube.com/watch?v=_ngCLZ5Iz-0", "duration": 680, "thumbnail": "", "order": 5, "completed": False, "watched_percent": 0},
                {"id": "v14", "title": "State Architecture Patterns", "url": "https://www.youtube.com/watch?v=HKU24nY8Hsc", "duration": 700, "thumbnail": "", "order": 6, "completed": False, "watched_percent": 0},
            ],
        },
        {
            "id": "course_003", "title": "Performance Optimization",
            "description": "React.memo, useMemo, code splitting, lazy loading, and profiling",
            "icon": "⚡", "category": "Frontend", "difficulty": "Advanced",
            "total_videos": 5, "completed_videos": 1, "progress": 28, "estimated_hours": 5,
            "tags": ["Performance", "Optimization", "React"],
            "video_links": [
                {"id": "v15", "title": "React Performance Basics", "url": "https://www.youtube.com/watch?v=b1IQI4aJHLM", "duration": 800, "thumbnail": "", "order": 1, "completed": True, "watched_percent": 100},
                {"id": "v16", "title": "React.memo & useMemo", "url": "https://www.youtube.com/watch?v=THL1OPn72vo", "duration": 700, "thumbnail": "", "order": 2, "completed": False, "watched_percent": 40},
                {"id": "v17", "title": "Code Splitting & Lazy Loading", "url": "https://www.youtube.com/watch?v=JU6sl_yyZqs", "duration": 650, "thumbnail": "", "order": 3, "completed": False, "watched_percent": 0},
                {"id": "v18", "title": "Profiler & DevTools", "url": "https://www.youtube.com/watch?v=LfEkP0bpFLc", "duration": 600, "thumbnail": "", "order": 4, "completed": False, "watched_percent": 0},
                {"id": "v19", "title": "Real-world Optimization Case Study", "url": "https://www.youtube.com/watch?v=i8xbddI2Mg8", "duration": 900, "thumbnail": "", "order": 5, "completed": False, "watched_percent": 0},
            ],
        },
    ]
    for course in courses:
        db.merge(Course(**course))
    logger.info(f"Seeded {len(courses)} courses")


def _seed_challenges(db: Session):
    challenges = [
        {"id": "dc1", "title": "Watch 30 minutes", "description": "Watch any video for 30 minutes", "xp_reward": 50, "type": "watch", "target": 30},
        {"id": "dc2", "title": "Perfect Quiz", "description": "Score 100% on any quiz", "xp_reward": 100, "type": "quiz", "target": 1},
        {"id": "dc3", "title": "Streak Keeper", "description": "Log in and study today", "xp_reward": 25, "type": "streak", "target": 1},
        {"id": "dc4", "title": "Review Master", "description": "Review 3 completed lessons", "xp_reward": 75, "type": "review", "target": 3},
    ]
    for c in challenges:
        db.merge(DailyChallenge(**c))
    logger.info("Seeded daily challenges")


def _seed_notifications(db: Session):
    notifs = [
        {"id": "n1", "type": "achievement", "title": "Welcome to NeuroLearn!", "message": "Create your account to start earning XP", "timestamp": "just now", "read": False, "icon": "🎉"},
    ]
    for n in notifs:
        db.merge(Notification(**n))
    logger.info("Seeded notifications")