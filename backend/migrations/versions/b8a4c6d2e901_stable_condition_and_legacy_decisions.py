"""stable condition assignment and legacy decisions

Revision ID: b8a4c6d2e901
Revises: f7d2a9c1b604
Create Date: 2026-08-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b8a4c6d2e901"
down_revision: Union[str, None] = "f7d2a9c1b604"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table_name)}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _indexes(table_name: str) -> set[str]:
    return {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    if "assigned_condition" not in _columns("research_participants"):
        op.add_column("research_participants", sa.Column("assigned_condition", sa.String(), nullable=True))
    if "ix_research_participants_assigned_condition" not in _indexes("research_participants"):
        op.create_index(
            op.f("ix_research_participants_assigned_condition"),
            "research_participants",
            ["assigned_condition"],
            unique=False,
        )
    op.execute(
        """
        UPDATE research_participants
        SET assigned_condition = CASE
            WHEN CAST(regexp_replace(participant_id, '^participant_', '') AS INTEGER) % 2 = 1
                THEN 'MCRF'
            ELSE 'LEGACY'
        END
        WHERE assigned_condition IS NULL
        """
    )
    constraints = {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints("research_participants")}
    if "ck_research_participants_assigned_condition" not in constraints:
        op.create_check_constraint(
            "ck_research_participants_assigned_condition",
            "research_participants",
            "assigned_condition IN ('MCRF', 'LEGACY')",
        )

    if "research_legacy_decisions" not in _tables():
        op.create_table(
            "research_legacy_decisions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("study_session_id", sa.String(), nullable=False),
        sa.Column("assessment_session_id", sa.String(), nullable=False),
        sa.Column("participant_id", sa.String(), nullable=False),
        sa.Column("condition", sa.String(), nullable=False),
        sa.Column("decision_index", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("performance_input", sa.Float(), nullable=True),
        sa.Column("performance_history", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("previous_difficulty", sa.String(), nullable=True),
        sa.Column("selected_difficulty", sa.String(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["assessment_session_id"], ["assessment_sessions.id"]),
        sa.ForeignKeyConstraint(["participant_id"], ["research_participants.participant_id"]),
        sa.ForeignKeyConstraint(["study_session_id"], ["study_sessions.study_session_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "study_session_id",
            "assessment_session_id",
            "decision_index",
            name="uq_research_legacy_decision_index",
        ),
        )
    legacy_indexes = _indexes("research_legacy_decisions")
    if "ix_research_legacy_decisions_assessment_session_id" not in legacy_indexes:
        op.create_index(op.f("ix_research_legacy_decisions_assessment_session_id"), "research_legacy_decisions", ["assessment_session_id"], unique=False)
    if "ix_research_legacy_decisions_condition" not in legacy_indexes:
        op.create_index(op.f("ix_research_legacy_decisions_condition"), "research_legacy_decisions", ["condition"], unique=False)
    if "ix_research_legacy_decisions_participant_id" not in legacy_indexes:
        op.create_index(op.f("ix_research_legacy_decisions_participant_id"), "research_legacy_decisions", ["participant_id"], unique=False)
    if "ix_research_legacy_decisions_study_session_id" not in legacy_indexes:
        op.create_index(op.f("ix_research_legacy_decisions_study_session_id"), "research_legacy_decisions", ["study_session_id"], unique=False)
    if "ix_research_legacy_decisions_timestamp" not in legacy_indexes:
        op.create_index(op.f("ix_research_legacy_decisions_timestamp"), "research_legacy_decisions", ["timestamp"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_research_legacy_decisions_timestamp"), table_name="research_legacy_decisions")
    op.drop_index(op.f("ix_research_legacy_decisions_study_session_id"), table_name="research_legacy_decisions")
    op.drop_index(op.f("ix_research_legacy_decisions_participant_id"), table_name="research_legacy_decisions")
    op.drop_index(op.f("ix_research_legacy_decisions_condition"), table_name="research_legacy_decisions")
    op.drop_index(op.f("ix_research_legacy_decisions_assessment_session_id"), table_name="research_legacy_decisions")
    op.drop_table("research_legacy_decisions")
    op.drop_constraint("ck_research_participants_assigned_condition", "research_participants", type_="check")
    op.drop_index(op.f("ix_research_participants_assigned_condition"), table_name="research_participants")
    op.drop_column("research_participants", "assigned_condition")
