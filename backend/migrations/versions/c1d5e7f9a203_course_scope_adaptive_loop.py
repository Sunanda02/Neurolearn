"""course scope and adaptive loop metadata

Revision ID: c1d5e7f9a203
Revises: b8a4c6d2e901
Create Date: 2026-08-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c1d5e7f9a203"
down_revision: Union[str, None] = "b8a4c6d2e901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    columns = _columns("assessment_sessions")
    if "contributing_video_ids" not in columns:
        op.add_column("assessment_sessions", sa.Column("contributing_video_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if "adaptive_state" not in columns:
        op.add_column("assessment_sessions", sa.Column("adaptive_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    columns = _columns("assessment_sessions")
    if "adaptive_state" in columns:
        op.drop_column("assessment_sessions", "adaptive_state")
    if "contributing_video_ids" in columns:
        op.drop_column("assessment_sessions", "contributing_video_ids")
