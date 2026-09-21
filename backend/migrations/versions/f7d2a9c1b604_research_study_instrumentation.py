"""research study instrumentation

Revision ID: f7d2a9c1b604
Revises: a4b7c2d9e103
Create Date: 2026-08-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f7d2a9c1b604"
down_revision: Union[str, Sequence[str], None] = "a4b7c2d9e103"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table_name)}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if table_name in _tables() and column.name not in _columns(table_name):
        op.add_column(table_name, column)


def _create_index(name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
    indexes = {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table_name)}
    if name not in indexes:
        op.create_index(name, table_name, columns, unique=unique)


def upgrade() -> None:
    tables = _tables()

    if "research_participants" not in tables:
        op.create_table(
            "research_participants",
            sa.Column("participant_id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("sequence_order", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint(
                "sequence_order IN ('MCRF_THEN_LEGACY', 'LEGACY_THEN_MCRF')",
                name="ck_research_participants_sequence_order",
            ),
        )
        _create_index("ix_research_participants_user_id", "research_participants", ["user_id"], unique=True)

    if "study_sessions" not in _tables():
        op.create_table(
            "study_sessions",
            sa.Column("study_session_id", sa.String(), primary_key=True),
            sa.Column("participant_id", sa.String(), sa.ForeignKey("research_participants.participant_id"), nullable=False),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("condition", sa.String(), nullable=False),
            sa.Column("sequence_order", sa.String(), nullable=False),
            sa.Column("course_id", sa.String(), nullable=True),
            sa.Column("module_id", sa.String(), nullable=True),
            sa.Column("video_id", sa.String(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("ended_at", sa.DateTime(), nullable=True),
            sa.Column("completion_status", sa.String(), nullable=True),
            sa.Column("experiment_version", sa.String(), nullable=True),
            sa.Column("application_version", sa.String(), nullable=True),
            sa.Column("crs_config_version", sa.String(), nullable=True),
            sa.Column("pretest_score", sa.Float(), nullable=True),
            sa.Column("posttest_score", sa.Float(), nullable=True),
            sa.Column("learning_gain", sa.Float(), nullable=True),
            sa.Column("camera_used", sa.Boolean(), nullable=True),
            sa.Column("camera_opted_out", sa.Boolean(), nullable=True),
            sa.Column("camera_revoked", sa.Boolean(), nullable=True),
            sa.CheckConstraint("condition IN ('MCRF', 'LEGACY')", name="ck_study_sessions_condition"),
        )
        for col in ["participant_id", "user_id", "condition", "course_id", "module_id", "video_id", "started_at", "completion_status", "experiment_version"]:
            _create_index(f"ix_study_sessions_{col}", "study_sessions", [col])

    for table_name in ["assessment_sessions", "crs_history", "attention_logs"]:
        if table_name not in _tables():
            continue
        additions = {
            "study_session_id": sa.Column("study_session_id", sa.String(), sa.ForeignKey("study_sessions.study_session_id"), nullable=True),
            "participant_id": sa.Column("participant_id", sa.String(), sa.ForeignKey("research_participants.participant_id"), nullable=True),
            "condition": sa.Column("condition", sa.String(), nullable=True),
        }
        for name, column in additions.items():
            if table_name == "attention_logs" and name == "condition":
                continue
            _add_column_if_missing(table_name, column)
            if name in _columns(table_name):
                _create_index(f"ix_{table_name}_{name}", table_name, [name])

    if "consent" in _tables():
        _add_column_if_missing("consent", sa.Column("study_session_id", sa.String(), sa.ForeignKey("study_sessions.study_session_id"), nullable=True))
        if "study_session_id" in _columns("consent"):
            _create_index("ix_consent_study_session_id", "consent", ["study_session_id"])

    if "assessment_sessions" in _tables():
        for column in [
            sa.Column("course_id", sa.String(), nullable=True),
            sa.Column("video_id", sa.String(), nullable=True),
            sa.Column("starting_difficulty", sa.String(), nullable=True),
            sa.Column("selected_difficulty", sa.String(), nullable=True),
            sa.Column("ending_difficulty", sa.String(), nullable=True),
            sa.Column("completion_status", sa.String(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("total_score", sa.Float(), nullable=True),
            sa.Column("percentage", sa.Float(), nullable=True),
            sa.Column("total_duration_seconds", sa.Float(), nullable=True),
            sa.Column("number_of_questions", sa.Integer(), nullable=True),
            sa.Column("number_correct", sa.Integer(), nullable=True),
        ]:
            _add_column_if_missing("assessment_sessions", column)

    if "question_responses" not in _tables():
        op.create_table(
            "question_responses",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("study_session_id", sa.String(), sa.ForeignKey("study_sessions.study_session_id"), nullable=False),
            sa.Column("assessment_session_id", sa.String(), sa.ForeignKey("assessment_sessions.id"), nullable=False),
            sa.Column("participant_id", sa.String(), sa.ForeignKey("research_participants.participant_id"), nullable=False),
            sa.Column("condition", sa.String(), nullable=False),
            sa.Column("question_id", sa.String(), nullable=False),
            sa.Column("question_index", sa.Integer(), nullable=False),
            sa.Column("question_difficulty", sa.String(), nullable=True),
            sa.Column("question_source", sa.String(), nullable=True),
            sa.Column("model_provider", sa.String(), nullable=True),
            sa.Column("live_fallback_status", sa.String(), nullable=True),
            sa.Column("bloom_level", sa.String(), nullable=True),
            sa.Column("presented_at", sa.DateTime(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
            sa.Column("response_time_seconds", sa.Float(), nullable=True),
            sa.Column("submitted_answer", sa.Text(), nullable=True),
            sa.Column("correctness", sa.Boolean(), nullable=True),
            sa.Column("score_points", sa.Float(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("study_session_id", "assessment_session_id", "question_id", name="uq_question_response_once"),
        )
        for col in ["study_session_id", "assessment_session_id", "participant_id", "condition", "question_id", "status"]:
            _create_index(f"ix_question_responses_{col}", "question_responses", [col])

    if "research_crs_decisions" not in _tables():
        op.create_table(
            "research_crs_decisions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("study_session_id", sa.String(), sa.ForeignKey("study_sessions.study_session_id"), nullable=False),
            sa.Column("assessment_session_id", sa.String(), sa.ForeignKey("assessment_sessions.id"), nullable=False),
            sa.Column("participant_id", sa.String(), sa.ForeignKey("research_participants.participant_id"), nullable=False),
            sa.Column("condition", sa.String(), nullable=False),
            sa.Column("decision_index", sa.Integer(), nullable=False),
            sa.Column("timestamp", sa.DateTime(), nullable=True),
            sa.Column("performance", sa.Float(), nullable=False),
            sa.Column("behavioral_cue", sa.Float(), nullable=False),
            sa.Column("response_timing", sa.Float(), nullable=False),
            sa.Column("trend", sa.Float(), nullable=False),
            sa.Column("complexity", sa.Float(), nullable=False),
            sa.Column("crs", sa.Float(), nullable=False),
            sa.Column("alpha", sa.Float(), nullable=False),
            sa.Column("beta", sa.Float(), nullable=False),
            sa.Column("gamma", sa.Float(), nullable=False),
            sa.Column("delta", sa.Float(), nullable=False),
            sa.Column("epsilon", sa.Float(), nullable=False),
            sa.Column("selected_difficulty", sa.String(), nullable=False),
            sa.Column("previous_difficulty", sa.String(), nullable=True),
            sa.Column("explanation", sa.Text(), nullable=True),
            sa.Column("performance_inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("timing_inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("trend_inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("complexity_inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.UniqueConstraint("study_session_id", "assessment_session_id", "decision_index", name="uq_research_crs_decision_index"),
        )
        for col in ["study_session_id", "assessment_session_id", "participant_id", "condition", "timestamp"]:
            _create_index(f"ix_research_crs_decisions_{col}", "research_crs_decisions", [col])

    if "behavioral_summaries" not in _tables():
        op.create_table(
            "behavioral_summaries",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("study_session_id", sa.String(), sa.ForeignKey("study_sessions.study_session_id"), nullable=False),
            sa.Column("participant_id", sa.String(), sa.ForeignKey("research_participants.participant_id"), nullable=False),
            sa.Column("condition", sa.String(), nullable=False),
            sa.Column("mean_b", sa.Float(), nullable=True),
            sa.Column("median_b", sa.Float(), nullable=True),
            sa.Column("stddev_b", sa.Float(), nullable=True),
            sa.Column("min_b", sa.Float(), nullable=True),
            sa.Column("max_b", sa.Float(), nullable=True),
            sa.Column("observation_count", sa.Integer(), nullable=True),
            sa.Column("behavioral_state_proportions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("camera_used", sa.Boolean(), nullable=True),
            sa.Column("camera_opted_out", sa.Boolean(), nullable=True),
            sa.Column("camera_revoked", sa.Boolean(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        _create_index("ix_behavioral_summaries_study_session_id", "behavioral_summaries", ["study_session_id"], unique=True)
        _create_index("ix_behavioral_summaries_participant_id", "behavioral_summaries", ["participant_id"])
        _create_index("ix_behavioral_summaries_condition", "behavioral_summaries", ["condition"])

    if "prepost_results" not in _tables():
        op.create_table(
            "prepost_results",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("study_session_id", sa.String(), sa.ForeignKey("study_sessions.study_session_id"), nullable=False),
            sa.Column("participant_id", sa.String(), sa.ForeignKey("research_participants.participant_id"), nullable=False),
            sa.Column("test_type", sa.String(), nullable=False),
            sa.Column("question_id", sa.String(), nullable=False),
            sa.Column("question_index", sa.Integer(), nullable=False),
            sa.Column("correctness", sa.Boolean(), nullable=True),
            sa.Column("response_time_seconds", sa.Float(), nullable=True),
            sa.Column("score", sa.Float(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("study_session_id", "test_type", "question_id", name="uq_prepost_question_once"),
        )
        for col in ["study_session_id", "participant_id", "test_type"]:
            _create_index(f"ix_prepost_results_{col}", "prepost_results", [col])

    if "generated_questions" not in _tables():
        op.create_table(
            "generated_questions",
            sa.Column("question_id", sa.String(), primary_key=True),
            sa.Column("study_session_id", sa.String(), sa.ForeignKey("study_sessions.study_session_id"), nullable=True),
            sa.Column("assessment_session_id", sa.String(), sa.ForeignKey("assessment_sessions.id"), nullable=True),
            sa.Column("model_version", sa.String(), nullable=True),
            sa.Column("generated_live_fallback", sa.String(), nullable=True),
            sa.Column("source_material", sa.String(), nullable=True),
            sa.Column("difficulty", sa.String(), nullable=True),
            sa.Column("bloom_level", sa.String(), nullable=True),
            sa.Column("generation_timestamp", sa.DateTime(), nullable=True),
            sa.Column("question_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
        _create_index("ix_generated_questions_study_session_id", "generated_questions", ["study_session_id"])
        _create_index("ix_generated_questions_assessment_session_id", "generated_questions", ["assessment_session_id"])


def downgrade() -> None:
    for table_name, cols in {
        "assessment_sessions": [
            "study_session_id", "participant_id", "condition", "course_id", "video_id",
            "starting_difficulty", "selected_difficulty", "ending_difficulty",
            "completion_status", "completed_at", "total_score", "percentage",
            "total_duration_seconds", "number_of_questions", "number_correct",
        ],
        "crs_history": ["study_session_id", "participant_id", "condition"],
        "attention_logs": ["study_session_id", "participant_id"],
        "consent": ["study_session_id"],
    }.items():
        if table_name not in _tables():
            continue
        existing = _columns(table_name)
        for col in cols:
            if col in existing:
                op.drop_column(table_name, col)

    for table_name in [
        "generated_questions",
        "prepost_results",
        "behavioral_summaries",
        "research_crs_decisions",
        "question_responses",
        "study_sessions",
        "research_participants",
    ]:
        if table_name in _tables():
            op.drop_table(table_name)
