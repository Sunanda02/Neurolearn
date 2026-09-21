import csv
from pathlib import Path

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.validate_research_export import REQUIRED_FILES, validate


def _write_csv(path: Path, rows: list[dict]):
    fieldnames = list(rows[0].keys()) if rows else ["id"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _minimal_export(tmp_path: Path):
    rows_by_file = {
        "participants.csv": [
            {
                "participant_id": "participant_001",
                "sequence_order": "MCRF_THEN_LEGACY",
                "assigned_condition": "MCRF",
                "created_at": "2026-08-17T00:00:00",
            }
        ],
        "study_sessions.csv": [
            {
                "study_session_id": "study_001", "participant_id": "participant_001",
                "condition": "MCRF", "sequence_order": "MCRF_THEN_LEGACY",
                "course_id": "course_001", "module_id": "course_001", "video_id": "v1",
                "started_at": "2026-08-17T00:00:00", "ended_at": "2026-08-17T00:10:00",
                "completion_status": "completed", "experiment_version": "full-study-v1",
                "application_version": "test", "crs_config_version": "crs-equal-weights-v1",
                "pretest_score": "1", "posttest_score": "2", "learning_gain": "1",
                "camera_used": "True", "camera_opted_out": "False", "camera_revoked": "True",
            }
        ],
        "study_video_completions.csv": [],
        "assessments.csv": [
            {
                "id": "assess_001", "study_session_id": "study_001",
                "participant_id": "participant_001", "condition": "MCRF",
                "course_id": "course_001", "video_id": "v1", "contributing_video_ids": "[\"v1\"]", "difficulty": "medium",
                "starting_difficulty": "medium", "selected_difficulty": "medium",
                "ending_difficulty": "hard", "total_score": "10", "percentage": "100",
                "total_duration_seconds": "30", "number_of_questions": "1",
                "number_correct": "1", "completion_status": "completed",
                "created_at": "2026-08-17T00:01:00", "completed_at": "2026-08-17T00:02:00",
            }
        ],
        "question_responses.csv": [
            {
                "id": "qr_001", "study_session_id": "study_001",
                "assessment_session_id": "assess_001", "participant_id": "participant_001",
                "condition": "MCRF", "question_id": "q1", "question_index": "0",
                "question_difficulty": "medium", "question_source": "fallback",
                "model_provider": "test", "live_fallback_status": "fallback",
                "bloom_level": "remember", "presented_at": "2026-08-17T00:01:00",
                "submitted_at": "2026-08-17T00:01:30", "response_time_seconds": "30",
                "submitted_answer": "0", "correctness": "True", "score_points": "10",
                "status": "submitted",
            }
        ],
        "crs_decisions.csv": [
            {
                "id": "crs_001", "study_session_id": "study_001",
                "assessment_session_id": "assess_001", "participant_id": "participant_001",
                "condition": "MCRF", "decision_index": "1", "timestamp": "2026-08-17T00:02:00",
                "performance": "1", "behavioral_cue": "0.8", "response_timing": "1",
                "trend": "0.5", "complexity": "0.5", "crs": "0.76",
                "alpha": "0.2", "beta": "0.2", "gamma": "0.2", "delta": "0.2",
                "epsilon": "0.2", "selected_difficulty": "hard",
                "previous_difficulty": "medium", "explanation": "test",
                "performance_inputs": "{}", "timing_inputs": "{}", "trend_inputs": "{}",
                "complexity_inputs": "{}", "detail": "{}",
            }
        ],
        "legacy_decisions.csv": [],
        "behavioral_summaries.csv": [
            {
                "id": "bs_001", "study_session_id": "study_001",
                "participant_id": "participant_001", "condition": "MCRF",
                "mean_b": "0.8", "median_b": "0.8", "stddev_b": "0",
                "min_b": "0.8", "max_b": "0.8", "observation_count": "1",
                "behavioral_state_proportions": "{}", "camera_used": "True",
                "camera_opted_out": "False", "camera_revoked": "True",
                "updated_at": "2026-08-17T00:02:00",
            }
        ],
        "prepost_results.csv": [
            {
                "id": "pre_001", "study_session_id": "study_001",
                "participant_id": "participant_001", "test_type": "pre",
                "question_id": "pre_q1", "question_index": "0",
                "correctness": "True", "response_time_seconds": "20", "score": "1",
                "started_at": "2026-08-17T00:00:00", "completed_at": "2026-08-17T00:00:20",
            }
        ],
        "generated_questions.csv": [
            {
                "question_id": "q1", "study_session_id": "study_001",
                "assessment_session_id": "assess_001", "model_version": "test",
                "generated_live_fallback": "fallback", "source_material": "v1",
                "difficulty": "medium", "bloom_level": "remember",
                "generation_timestamp": "2026-08-17T00:01:00", "question_metadata": "{}",
            }
        ],
    }
    for name in REQUIRED_FILES:
        _write_csv(tmp_path / name, rows_by_file[name])


def test_research_export_validator_passes_minimal_joinable_dataset(tmp_path):
    _minimal_export(tmp_path)
    _, warnings, failures = validate(tmp_path)
    assert warnings == []
    assert failures == []


def test_research_export_validator_fails_duplicate_question_response(tmp_path):
    _minimal_export(tmp_path)
    path = tmp_path / "question_responses.csv"
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    rows.append(dict(rows[0], id="qr_002"))
    _write_csv(path, rows)
    _, _, failures = validate(tmp_path)
    assert any("duplicate question response" in failure for failure in failures)


def test_prepost_duplicate_rows_are_validation_failures(tmp_path):
    _minimal_export(tmp_path)
    path = tmp_path / "prepost_results.csv"
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    rows.append(dict(rows[0], id="pre_002"))
    _write_csv(path, rows)
    _, _, failures = validate(tmp_path)
    assert any("duplicate pre/post response" in failure for failure in failures)
