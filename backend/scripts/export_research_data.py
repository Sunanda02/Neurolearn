"""Export anonymized NeuroLearn study data to CSV.

Run from repository root:
    cd backend
    python scripts/export_research_data.py --out exports/research_full-study-v1

The export intentionally omits auth/user email/name fields. Stable joins use
participant_id and study_session_id.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.db import SessionLocal
from data.models_orm import (
    AssessmentSession,
    BehavioralSummary,
    GeneratedQuestion,
    PrePostResult,
    QuestionResponse,
    ResearchCRSDecision,
    ResearchLegacyDecision,
    ResearchParticipant,
    StudySession,
    StudyVideoCompletion,
)


EXPORTS = {
    "participants": (
        ResearchParticipant,
        ["participant_id", "sequence_order", "assigned_condition", "created_at"],
    ),
    "study_sessions": (
        StudySession,
        [
            "study_session_id", "participant_id", "condition", "sequence_order",
            "course_id", "module_id", "video_id", "started_at", "ended_at",
            "completion_status", "experiment_version", "application_version",
            "crs_config_version", "pretest_score", "posttest_score",
            "learning_gain", "camera_used", "camera_opted_out", "camera_revoked",
        ],
    ),
    "study_video_completions": (
        StudyVideoCompletion,
        [
            "id", "study_session_id", "participant_id", "video_id",
            "completion_order", "completed_at", "transcript_text",
        ],
    ),
    "assessments": (
        AssessmentSession,
        [
            "id", "study_session_id", "participant_id", "condition", "course_id",
            "video_id", "contributing_video_ids", "difficulty", "starting_difficulty", "selected_difficulty",
            "ending_difficulty", "total_score", "percentage",
            "total_duration_seconds", "number_of_questions", "number_correct",
            "completion_status", "created_at", "completed_at", "questions",
            "adaptive_state", "transcript_text",
        ],
    ),
    "question_responses": (
        QuestionResponse,
        [
            "id", "study_session_id", "assessment_session_id", "participant_id",
            "condition", "question_id", "question_index", "question_difficulty",
            "question_source", "model_provider", "live_fallback_status",
            "bloom_level", "presented_at", "submitted_at", "response_time_seconds",
            "submitted_answer", "correctness", "score_points", "status",
        ],
    ),
    "crs_decisions": (
        ResearchCRSDecision,
        [
            "id", "study_session_id", "assessment_session_id", "participant_id",
            "condition", "decision_index", "timestamp", "performance",
            "behavioral_cue", "response_timing", "trend", "complexity", "crs",
            "alpha", "beta", "gamma", "delta", "epsilon", "selected_difficulty",
            "previous_difficulty", "explanation", "performance_inputs",
            "timing_inputs", "trend_inputs", "complexity_inputs", "detail",
        ],
    ),
    "legacy_decisions": (
        ResearchLegacyDecision,
        [
            "id", "study_session_id", "assessment_session_id", "participant_id",
            "condition", "decision_index", "timestamp", "performance_input",
            "performance_history", "previous_difficulty", "selected_difficulty",
            "explanation", "detail",
        ],
    ),
    "behavioral_summaries": (
        BehavioralSummary,
        [
            "id", "study_session_id", "participant_id", "condition", "mean_b",
            "median_b", "stddev_b", "min_b", "max_b", "observation_count",
            "behavioral_state_proportions", "camera_used", "camera_opted_out",
            "camera_revoked", "updated_at",
        ],
    ),
    "prepost_results": (
        PrePostResult,
        [
            "id", "study_session_id", "participant_id", "test_type",
            "question_id", "question_index", "correctness",
            "response_time_seconds", "score", "started_at", "completed_at",
        ],
    ),
    "generated_questions": (
        GeneratedQuestion,
        [
            "question_id", "study_session_id", "assessment_session_id",
            "model_version", "generated_live_fallback", "source_material",
            "difficulty", "bloom_level", "generation_timestamp",
            "question_metadata",
        ],
    ),
}

RESEARCH_LINKED_MODELS = {
    AssessmentSession,
    GeneratedQuestion,
}


def _csv_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return value


def export_dataset(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    db = SessionLocal()
    try:
        for name, (model, fields) in EXPORTS.items():
            path = out_dir / f"{name}.csv"
            stmt = select(model)
            if model in RESEARCH_LINKED_MODELS:
                stmt = stmt.where(model.study_session_id.is_not(None))
            rows = db.execute(stmt).scalars().all()
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                for row in rows:
                    writer.writerow({field: _csv_value(getattr(row, field)) for field in fields})
            written.append(path)
    finally:
        db.close()
    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="Output directory for CSV exports")
    args = parser.parse_args()
    written = export_dataset(Path(args.out))
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
