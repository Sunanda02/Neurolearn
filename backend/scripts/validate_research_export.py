"""Validate exported NeuroLearn research CSVs.

Run:
    cd backend
    python scripts/validate_research_export.py --dir exports/research_full-study-v1
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REQUIRED_FILES = [
    "participants.csv",
    "study_sessions.csv",
    "study_video_completions.csv",
    "assessments.csv",
    "question_responses.csv",
    "crs_decisions.csv",
    "legacy_decisions.csv",
    "behavioral_summaries.csv",
    "prepost_results.csv",
    "generated_questions.csv",
]
DIFFICULTIES = {"easy", "medium", "hard", ""}
CONDITIONS = {"MCRF", "LEGACY", "MIXED"}


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _float(value: str):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def validate(export_dir: Path) -> tuple[list[str], list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    passes: list[str] = []

    data = {name: _read(export_dir / name) for name in REQUIRED_FILES}
    for name, rows in data.items():
        if not (export_dir / name).exists():
            failures.append(f"FAIL missing file: {name}")
        else:
            passes.append(f"PASS loaded {name}: {len(rows)} rows")

    participants = {r.get("participant_id") for r in data["participants.csv"]}
    sessions = {r.get("study_session_id"): r for r in data["study_sessions.csv"]}
    assessments = {r.get("id"): r for r in data["assessments.csv"]}

    for table_name in [
        "study_sessions.csv", "study_video_completions.csv", "assessments.csv", "question_responses.csv",
        "crs_decisions.csv", "legacy_decisions.csv", "behavioral_summaries.csv", "prepost_results.csv",
        "generated_questions.csv",
    ]:
        for i, row in enumerate(data[table_name], start=2):
            study_session_id = row.get("study_session_id", "")
            if table_name != "generated_questions.csv" or study_session_id:
                if not study_session_id:
                    failures.append(f"FAIL {table_name}:{i} missing study_session_id")
                elif study_session_id not in sessions:
                    failures.append(f"FAIL {table_name}:{i} orphan study_session_id={study_session_id}")
            participant_id = row.get("participant_id", "")
            if participant_id and participant_id not in participants:
                failures.append(f"FAIL {table_name}:{i} orphan participant_id={participant_id}")
            condition = row.get("condition", "")
            if condition and condition not in CONDITIONS:
                failures.append(f"FAIL {table_name}:{i} invalid condition={condition}")

    seen_responses = Counter(
        (
            r.get("study_session_id"),
            r.get("assessment_session_id"),
            r.get("question_id"),
        )
        for r in data["question_responses.csv"]
    )
    for key, count in seen_responses.items():
        if count > 1:
            failures.append(f"FAIL duplicate question response: {key}")

    seen_prepost = Counter(
        (
            r.get("study_session_id"),
            r.get("test_type"),
            r.get("question_id"),
        )
        for r in data["prepost_results.csv"]
    )
    for key, count in seen_prepost.items():
        if count > 1:
            failures.append(f"FAIL duplicate pre/post response: {key}")

    for i, row in enumerate(data["question_responses.csv"], start=2):
        assessment_id = row.get("assessment_session_id")
        if assessment_id not in assessments:
            failures.append(f"FAIL question_responses.csv:{i} orphan assessment_session_id={assessment_id}")
        response_time = _float(row.get("response_time_seconds", ""))
        if response_time is not None and (response_time < 0 or response_time > 86400):
            failures.append(f"FAIL question_responses.csv:{i} impossible response_time_seconds={response_time}")
        if not row.get("condition"):
            failures.append(f"FAIL question_responses.csv:{i} missing condition")
        elif row.get("condition") not in {"MCRF", "LEGACY"}:
            failures.append(f"FAIL question_responses.csv:{i} invalid decision method={row.get('condition')}")

    for i, row in enumerate(data["crs_decisions.csv"], start=2):
        missing = [
            field for field in ["performance", "behavioral_cue", "response_timing", "trend", "complexity", "crs"]
            if row.get(field, "") == ""
        ]
        if missing:
            failures.append(f"FAIL crs_decisions.csv:{i} missing CRS components: {missing}")
        crs = _float(row.get("crs", ""))
        if crs is not None and not (0.0 <= crs <= 1.0):
            failures.append(f"FAIL crs_decisions.csv:{i} CRS outside [0,1]: {crs}")
        if row.get("selected_difficulty", "") not in DIFFICULTIES:
            failures.append(f"FAIL crs_decisions.csv:{i} invalid selected_difficulty={row.get('selected_difficulty')}")
        if row.get("condition") != "MCRF":
            failures.append(f"FAIL crs_decisions.csv:{i} CRS decision stored for non-MCRF condition")

    for i, row in enumerate(data["legacy_decisions.csv"], start=2):
        assessment_id = row.get("assessment_session_id")
        if assessment_id not in assessments:
            failures.append(f"FAIL legacy_decisions.csv:{i} orphan assessment_session_id={assessment_id}")
        if row.get("condition") != "LEGACY":
            failures.append(f"FAIL legacy_decisions.csv:{i} legacy decision stored for condition={row.get('condition')}")
        if row.get("selected_difficulty", "") not in DIFFICULTIES:
            failures.append(f"FAIL legacy_decisions.csv:{i} invalid selected_difficulty={row.get('selected_difficulty')}")

    for i, row in enumerate(data["assessments.csv"], start=2):
        if row.get("difficulty", "") not in DIFFICULTIES:
            failures.append(f"FAIL assessments.csv:{i} invalid difficulty={row.get('difficulty')}")
        study = sessions.get(row.get("study_session_id"))
        if study and row.get("condition") and row["condition"] != study.get("condition"):
            failures.append(f"FAIL assessments.csv:{i} inconsistent condition")
        if not row.get("created_at"):
            warnings.append(f"WARN assessments.csv:{i} missing started timestamp")

    for study_id, row in sessions.items():
        if not row.get("condition"):
            failures.append(f"FAIL study_sessions.csv missing condition for {study_id}")
        if not row.get("started_at"):
            failures.append(f"FAIL study_sessions.csv missing started_at for {study_id}")

    completions_by_study: dict[str, list[dict]] = {}
    for row in data["study_video_completions.csv"]:
        completions_by_study.setdefault(row.get("study_session_id", ""), []).append(row)
    for study_id, completions in completions_by_study.items():
        order = [int(row["completion_order"]) for row in completions if row.get("completion_order", "").isdigit()]
        if sorted(order) != list(range(1, len(completions) + 1)):
            failures.append(f"FAIL study_video_completions.csv invalid completion order for {study_id}")
        ids = [row.get("video_id") for row in sorted(completions, key=lambda value: int(value.get("completion_order") or 0))]
        if len(ids) != len(set(ids)):
            failures.append(f"FAIL study_video_completions.csv duplicate completed video for {study_id}")

    crs_by_assessment: dict[str, list[dict]] = {}
    for row in data["crs_decisions.csv"]:
        crs_by_assessment.setdefault(row.get("assessment_session_id", ""), []).append(row)
    legacy_by_assessment: dict[str, list[dict]] = {}
    for row in data["legacy_decisions.csv"]:
        legacy_by_assessment.setdefault(row.get("assessment_session_id", ""), []).append(row)
    responses_by_assessment: dict[str, list[dict]] = {}
    for row in data["question_responses.csv"]:
        responses_by_assessment.setdefault(row.get("assessment_session_id", ""), []).append(row)

    for assessment_id, assessment in assessments.items():
        if assessment.get("condition") != "MIXED":
            continue  # historical, one-method exports remain valid.
        study_id = assessment.get("study_session_id", "")
        completed_videos = sorted(
            completions_by_study.get(study_id, []),
            key=lambda value: int(value.get("completion_order") or 0),
        )
        try:
            contributors = json.loads(assessment.get("contributing_video_ids") or "[]")
        except json.JSONDecodeError:
            failures.append(f"FAIL assessments.csv invalid contributing_video_ids for {assessment_id}")
            contributors = []
        if contributors != [row.get("video_id") for row in completed_videos]:
            failures.append(f"FAIL assessments.csv contributing videos do not match completed order for {assessment_id}")

        is_completed = assessment.get("completion_status") == "completed"
        if not is_completed:
            continue
        responses = sorted(
            responses_by_assessment.get(assessment_id, []),
            key=lambda value: int(value.get("question_index") or -1),
        )
        if len(responses) != 10:
            failures.append(f"FAIL mixed assessment {assessment_id} has {len(responses)} responses; expected 10")
            continue
        if [row.get("question_index") for row in responses] != [str(index) for index in range(10)]:
            failures.append(f"FAIL mixed assessment {assessment_id} has non-sequential question indexes")
        if [row.get("condition") for row in responses] != ["MCRF"] * 5 + ["LEGACY"] * 5:
            failures.append(f"FAIL mixed assessment {assessment_id} does not use MCRF then LEGACY response segments")
        crs_indexes = sorted(int(row.get("decision_index") or 0) for row in crs_by_assessment.get(assessment_id, []))
        legacy_indexes = sorted(int(row.get("decision_index") or 0) for row in legacy_by_assessment.get(assessment_id, []))
        if crs_indexes != [1, 2, 3, 4, 5]:
            failures.append(f"FAIL mixed assessment {assessment_id} has MCRF decisions {crs_indexes}; expected 1-5")
        if legacy_indexes != [6, 7, 8, 9, 10]:
            failures.append(f"FAIL mixed assessment {assessment_id} has LEGACY decisions {legacy_indexes}; expected 6-10")

    if not failures:
        passes.append("PASS no failing integrity checks")
    return passes, warnings, failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, help="Directory created by export_research_data.py")
    args = parser.parse_args()
    passes, warnings, failures = validate(Path(args.dir))
    for line in passes + warnings + failures:
        print(line)
    if failures:
        return 2
    if warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
