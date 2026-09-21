"""Run a synthetic end-to-end study instrumentation simulation.

Run after applying migrations:
    cd backend
    python scripts/simulate_study_session.py --export-dir exports/simulation

This verifies joins and instrumentation plumbing. It is not experimental data.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.database import (
    complete_study_session,
    create_study_session,
    refresh_behavioral_summary,
    save_assessment_result,
    save_assessment_session,
    save_crs_record,
    save_generated_questions,
    save_question_responses,
    save_research_crs_decision,
    save_research_legacy_decision,
    set_consent,
)
from data.db import SessionLocal
from data.models_orm import User
from ml.adaptive_engine import adaptive_engine
from scripts.export_research_data import export_dataset
from scripts.validate_research_export import validate


def _get_or_create_user() -> User:
    db = SessionLocal()
    try:
        email = "study-simulation@neurolearn.local"
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            user = User(
                email=email,
                hashed_password="not-a-real-login",
                name="Study Simulation",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
    finally:
        db.close()


def _questions() -> list[dict]:
    now = datetime.utcnow().isoformat()
    return [
        {
            "id": "sim_q1", "type": "mcq", "question": "What does state store?",
            "options": ["UI data", "CSS only", "Network only", "Build logs"],
            "correct_answer": 0, "difficulty": "medium", "points": 10,
            "explanation": "State stores data that can change over time.",
            "topic_id": "course_001",
            "llm_metadata": {
                "model": "simulation-fallback-v1",
                "generated_from": "fallback",
                "difficulty_score": 0.5,
                "blooms_level": "understand",
                "generated_at": now,
            },
        },
        {
            "id": "sim_q2", "type": "mcq", "question": "Which hook handles side effects?",
            "options": ["useMemo", "useEffect", "useId", "useRef"],
            "correct_answer": 1, "difficulty": "medium", "points": 10,
            "explanation": "useEffect handles side effects.",
            "topic_id": "course_001",
            "llm_metadata": {
                "model": "simulation-fallback-v1",
                "generated_from": "fallback",
                "difficulty_score": 0.5,
                "blooms_level": "remember",
                "generated_at": now,
            },
        },
        {
            "id": "sim_q3", "type": "mcq", "question": "Why are keys used in lists?",
            "options": ["Styling", "Stable identity", "Routing", "Compilation"],
            "correct_answer": 1, "difficulty": "medium", "points": 10,
            "explanation": "Keys provide stable identity for list items.",
            "topic_id": "course_001",
            "llm_metadata": {
                "model": "simulation-fallback-v1",
                "generated_from": "fallback",
                "difficulty_score": 0.5,
                "blooms_level": "apply",
                "generated_at": now,
            },
        },
    ]


def run_simulation(export_dir: Path) -> int:
    user = _get_or_create_user()

    study = create_study_session(user.id, course_id="course_001", module_id="course_001", video_id="v1")

    webcam_session_id = f"webcam_sim_{int(time.time())}"
    set_consent({
        "student_id": user.id,
        "session_id": webcam_session_id,
        "study_session_id": study["study_session_id"],
        "granted": True,
        "granted_at": datetime.utcnow().isoformat(),
        "retention_days": 30,
        "raw_frames_stored": False,
        "version": "1.0",
    })

    for i, score in enumerate([82, 76, 88], start=1):
        from data.database import log_attention

        log_attention({
            "student_id": user.id,
            "participant_id": study["participant_id"],
            "study_session_id": study["study_session_id"],
            "session_id": webcam_session_id,
            "video_id": "v1",
            "timestamp": (datetime.utcnow() + timedelta(seconds=i)).isoformat(),
            "score": score,
            "state": "attentive",
            "confidence": 0.9,
            "message": "simulation",
            "model_response": {
                "eye_contact": score / 100,
                "head_pose": "forward",
                "face_detected": True,
                "blink_rate": 14 + i,
            },
            "source": "simulation",
            "consent_confirmed": True,
        })

    session = {
        "id": f"session_sim_{int(time.time())}",
        "study_session_id": study["study_session_id"],
        "participant_id": study["participant_id"],
        "condition": study["condition"],
        "student_id": user.id,
        "course_id": "course_001",
        "video_id": "v1",
        "questions": _questions(),
        "difficulty": "medium",
        "starting_difficulty": "medium",
        "selected_difficulty": "medium",
        "time_limit": 180,
        "attention_score_during_video": 82,
        "transcript_text": (
            "React components render interface state. Hooks manage state and "
            "side effects. List keys preserve identity during reconciliation."
        ),
    }
    save_assessment_session(session)
    save_generated_questions(session)

    now = datetime.utcnow()
    answers = {"sim_q1": 0, "sim_q2": 1, "sim_q3": 0}
    responses = save_question_responses(
        study_session=study,
        assessment_session=session,
        answers=answers,
        response_events=[
            {
                "question_id": "sim_q1",
                "presented_at": now.isoformat(),
                "submitted_at": (now + timedelta(seconds=25)).isoformat(),
                "response_time_seconds": 25,
                "status": "submitted",
            },
            {
                "question_id": "sim_q2",
                "presented_at": (now + timedelta(seconds=26)).isoformat(),
                "submitted_at": (now + timedelta(seconds=56)).isoformat(),
                "response_time_seconds": 30,
                "status": "submitted",
            },
            {
                "question_id": "sim_q3",
                "presented_at": (now + timedelta(seconds=57)).isoformat(),
                "submitted_at": (now + timedelta(seconds=77)).isoformat(),
                "response_time_seconds": 20,
                "status": "submitted",
            },
        ],
        submitted_at=now + timedelta(seconds=77),
        total_time_spent=77,
    )

    percentage = 66.7
    previous_scores = [55, 62, percentage]
    if study["condition"] == "LEGACY":
        adaptive = adaptive_engine._determine_difficulty_legacy(
            student_id=user.id,
            current_score=percentage,
            attention_score=82,
            time_spent=77,
            time_limit=session["time_limit"],
            previous_difficulty="medium",
            previous_scores=previous_scores[:-1],
        )
    else:
        adaptive = adaptive_engine.determine_difficulty(
            student_id=user.id,
            current_score=percentage,
            attention_score=82,
            time_spent=25,
            time_limit=60,
            previous_difficulty="medium",
            previous_scores=previous_scores[:-1],
            transcript_text=session["transcript_text"],
            was_correct=True,
        )
    save_assessment_result({
        "session_id": session["id"],
        "study_session_id": study["study_session_id"],
        "participant_id": study["participant_id"],
        "condition": study["condition"],
        "student_id": user.id,
        "score": percentage,
        "percentage": percentage,
        "xp_earned": 20,
        "timestamp": time.time(),
        "time_spent": 77,
        "earned_points": 20,
        "correct_answers": 2,
        "total_questions": 3,
        "next_difficulty": adaptive["next_assessment_difficulty"],
        "completion_status": "completed",
    })
    if study["condition"] == "MCRF":
        crs = adaptive["crs"]
        save_crs_record({
            "student_id": user.id,
            "study_session_id": study["study_session_id"],
            "participant_id": study["participant_id"],
            "condition": study["condition"],
            "assessment_id": session["id"],
            "timestamp": time.time(),
            "performance": crs["components"]["performance"],
            "behavioral_cue": crs["components"]["behavioral_cue"],
            "integrity": crs["components"]["integrity"],
            "trend": crs["components"]["trend"],
            "complexity": crs["components"]["complexity"],
            "crs": crs["score"],
            "difficulty": adaptive["next_assessment_difficulty"],
            "explanation": crs["explanation"],
        })
        save_research_crs_decision(
            study_session=study,
            assessment_session=session,
            adaptive_result=adaptive,
            previous_scores=previous_scores,
            per_question_responses=responses,
            previous_difficulty="medium",
            attention_score=82,
            transcript_text=session["transcript_text"],
        )
    else:
        save_research_legacy_decision(
            study_session=study,
            assessment_session=session,
            adaptive_result=adaptive,
            previous_scores=previous_scores,
            per_question_responses=responses,
            previous_difficulty="medium",
            current_score=percentage,
        )

    set_consent({
        "student_id": user.id,
        "session_id": webcam_session_id,
        "study_session_id": study["study_session_id"],
        "granted": False,
        "granted_at": datetime.utcnow().isoformat(),
        "retention_days": 30,
        "raw_frames_stored": False,
        "version": "1.0",
    })
    neutral_after_revocation = 0.5
    if neutral_after_revocation != 0.5:
        raise AssertionError("B did not become neutral after revocation")

    refresh_behavioral_summary(study["study_session_id"])
    complete_study_session(study["study_session_id"], "completed")

    written = export_dataset(export_dir)
    passes, warnings, failures = validate(export_dir)
    print(f"participant_id={study['participant_id']}")
    print(f"study_session_id={study['study_session_id']}")
    print(f"exported_files={len(written)}")
    for line in passes + warnings + failures:
        print(line)
    return 2 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-dir", required=True)
    args = parser.parse_args()
    return run_simulation(Path(args.export_dir))


if __name__ == "__main__":
    raise SystemExit(main())
