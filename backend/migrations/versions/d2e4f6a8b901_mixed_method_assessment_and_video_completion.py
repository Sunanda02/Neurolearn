"""mixed-method assessment protocol and completed-video audit trail

Revision ID: d2e4f6a8b901
Revises: b8a4c6d2e901
Create Date: 2026-08-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2e4f6a8b901"
down_revision: Union[str, None] = "b8a4c6d2e901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    if "study_video_completions" not in _tables():
        op.create_table(
            "study_video_completions",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("study_session_id", sa.String(), nullable=False),
            sa.Column("participant_id", sa.String(), nullable=False),
            sa.Column("video_id", sa.String(), nullable=False),
            sa.Column("completion_order", sa.Integer(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=False),
            sa.Column("transcript_text", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["participant_id"], ["research_participants.participant_id"]),
            sa.ForeignKeyConstraint(["study_session_id"], ["study_sessions.study_session_id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("study_session_id", "video_id", name="uq_study_video_completion_once"),
            sa.UniqueConstraint("study_session_id", "completion_order", name="uq_study_video_completion_order"),
        )

    indexes = _indexes("study_video_completions")
    for name, columns in {
        "ix_study_video_completions_study_session_id": ["study_session_id"],
        "ix_study_video_completions_participant_id": ["participant_id"],
        "ix_study_video_completions_video_id": ["video_id"],
        "ix_study_video_completions_completed_at": ["completed_at"],
    }.items():
        if name not in indexes:
            op.create_index(name, "study_video_completions", columns, unique=False)

    # A study session and its one assessment now contain both experimental
    # segments.  Historical MCRF-only / LEGACY-only rows remain valid; new
    # sessions use MIXED and each response/decision carries its own method.
    constraints = {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_check_constraints("study_sessions")
    }
    if "ck_study_sessions_condition" in constraints:
        op.drop_constraint("ck_study_sessions_condition", "study_sessions", type_="check")
        op.create_check_constraint(
            "ck_study_sessions_condition",
            "study_sessions",
            "condition IN ('MCRF', 'LEGACY', 'MIXED')",
        )

    participant_constraints = {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_check_constraints("research_participants")
    }
    if "ck_research_participants_assigned_condition" in participant_constraints:
        op.drop_constraint(
            "ck_research_participants_assigned_condition",
            "research_participants",
            type_="check",
        )
        op.create_check_constraint(
            "ck_research_participants_assigned_condition",
            "research_participants",
            "assigned_condition IN ('MCRF', 'LEGACY', 'MIXED')",
        )


def downgrade() -> None:
    op.drop_table("study_video_completions")
