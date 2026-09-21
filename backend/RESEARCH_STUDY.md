# NeuroLearn Research Study Instrumentation

This document describes the data collection added for `full-study-v1`. It is instrumentation only: it does not change CRS weights, CRS thresholds, MCL-DE logic, or the legacy adaptive policy.

## Study Setup

1. Apply migrations from `backend`:
   `alembic upgrade head`
2. Start the backend normally:
   `python main.py`
3. A learner session can be created explicitly with `POST /api/research/study-sessions`, or automatically when `/api/assessment/generate` is called without an existing `study_session_id`.
4. Experimental condition is assigned server-side. The frontend may pass `study_session_id`, but cannot select `MCRF` or `LEGACY`.
5. Counterbalancing alternates by pseudonymous participant:
   `MCRF_THEN_LEGACY`, then `LEGACY_THEN_MCRF`.

## Participant Session Flow

`research_participants.participant_id` is pseudonymous, for example `participant_001`.

The join path for a complete session is:

`participant_id -> study_session_id -> assessment_sessions.id -> question_responses.assessment_session_id`

Webcam-derived records use the same `study_session_id` when available. Raw webcam frames are not stored.

## Data Dictionary

`research_participants`

- `participant_id`: pseudonymous research identifier.
- `user_id`: internal auth user foreign key; excluded from CSV export.
- `sequence_order`: `MCRF_THEN_LEGACY` or `LEGACY_THEN_MCRF`.
- `created_at`: participant record creation time.

`study_sessions`

- `study_session_id`: stable study-level join key.
- `participant_id`: pseudonymous participant key.
- `user_id`: internal authenticated user key; excluded from export.
- `condition`: server-assigned `MCRF` or `LEGACY`.
- `sequence_order`: counterbalanced order assigned to participant.
- `course_id`, `module_id`, `video_id`: learning material identifiers.
- `started_at`, `ended_at`, `completion_status`: lifecycle fields.
- `experiment_version`: currently `full-study-v1`.
- `application_version`: git short commit when available.
- `crs_config_version`: currently `crs-equal-weights-v1`.
- `pretest_score`, `posttest_score`, `learning_gain`: pre/post totals, where `learning_gain = posttest_score - pretest_score`.
- `camera_used`, `camera_opted_out`, `camera_revoked`: session camera state.

`assessment_sessions`

- `study_session_id`, `participant_id`, `condition`: research linkage.
- `course_id`, `video_id`: material linkage.
- `difficulty`, `starting_difficulty`, `selected_difficulty`, `ending_difficulty`: assessment difficulty tracking.
- `total_score`, `percentage`, `total_duration_seconds`, `number_of_questions`, `number_correct`: aggregate outcome.
- `completion_status`, `created_at`, `completed_at`: lifecycle fields.

`question_responses`

- `study_session_id`, `assessment_session_id`, `participant_id`, `condition`: join keys and condition.
- `question_id`, `question_index`: item identity and order.
- `question_difficulty`, `question_source`, `model_provider`, `live_fallback_status`, `bloom_level`: question provenance.
- `presented_at`, `submitted_at`, `response_time_seconds`: per-question timing.
- `submitted_answer`, `correctness`, `score_points`, `status`: response outcome. `status` supports `submitted`, `unanswered`, `timeout`, `refresh`, and `retry`.

`research_crs_decisions`

- `study_session_id`, `assessment_session_id`, `participant_id`, `condition`: join keys.
- `decision_index`, `timestamp`: order and time.
- `performance`, `behavioral_cue`, `response_timing`, `trend`, `complexity`, `crs`: CRS inputs and result.
- `alpha`, `beta`, `gamma`, `delta`, `epsilon`: CRS weights used.
- `selected_difficulty`, `previous_difficulty`, `explanation`: decision output.
- `performance_inputs`, `timing_inputs`, `trend_inputs`, `complexity_inputs`, `detail`: reproducibility snapshots.

`attention_logs`

- Stores derived behavioral observations only: score, state, confidence, consent flag, model response fields, source, timestamps, and session identifiers.

`behavioral_summaries`

- `mean_b`, `median_b`, `stddev_b`, `min_b`, `max_b`, `observation_count`: session-level B summary.
- `behavioral_state_proportions`: state distribution.
- `camera_used`, `camera_opted_out`, `camera_revoked`: camera status summary.

`prepost_results`

- `study_session_id`, `participant_id`, `test_type`: pre/post linkage.
- `question_id`, `question_index`, `correctness`, `response_time_seconds`, `score`, `started_at`, `completed_at`: item-level pre/post result.

`generated_questions`

- `question_id`, `study_session_id`, `assessment_session_id`: item linkage.
- `model_version`, `generated_live_fallback`, `source_material`, `difficulty`, `bloom_level`, `generation_timestamp`, `question_metadata`: generation provenance.

## Export Procedure

Research export is script-only and excludes ordinary learner-facing routes:

`python scripts/export_research_data.py --out exports/research_full-study-v1`

Then validate:

`python scripts/validate_research_export.py --dir exports/research_full-study-v1`

The export writes:

- `participants.csv`
- `study_sessions.csv`
- `assessments.csv`
- `question_responses.csv`
- `crs_decisions.csv`
- `behavioral_summaries.csv`
- `prepost_results.csv`
- `generated_questions.csv`

## End-to-End Simulation

Run:

`python scripts/simulate_study_session.py --export-dir exports/simulation`

The simulation creates a synthetic local study session, webcam-derived observations, per-question responses, a CRS decision, consent revocation, pre/post rows, CSV export, and validation output. It is a plumbing test only and must not be reported as study evidence.
