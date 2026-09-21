"""study participation consent (A-2)

Adds the study_consent table — study-participation consent, separate
from webcam/camera consent (the `consent` table). One row per user.
Checked as the single gate before any research record
(ResearchParticipant / StudySession, and anything keyed off a
study_session_id downstream of it) is created.

Revision ID: e5f8b1c3d704
Revises: a1c9f47d8e02
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e5f8b1c3d704"
down_revision: Union[str, Sequence[str], None] = "a1c9f47d8e02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "study_consent" in tables:
        return

    op.create_table(
        "study_consent",
        sa.Column("student_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("granted", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("granted_at", sa.DateTime(), nullable=True),
        sa.Column("version", sa.String(), nullable=True, server_default="1.0"),
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "study_consent" in tables:
        op.drop_table("study_consent")