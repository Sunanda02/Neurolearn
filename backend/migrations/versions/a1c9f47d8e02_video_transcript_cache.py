"""persistent video transcript cache (survives backend restarts)

Revision ID: a1c9f47d8e02
Revises: 6e8014c01606
Create Date: 2026-09-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a1c9f47d8e02"
down_revision: Union[str, None] = "6e8014c01606"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    # Global, video_url-keyed cache of real Whisper transcripts —
    # deliberately separate from study_video_completions.transcript_text
    # (the per-session audit trail), so the same video's transcript is
    # reusable across every study session/student without a re-download or
    # re-transcription, and survives a backend restart.
    if "video_transcript_cache" not in _tables():
        op.create_table(
            "video_transcript_cache",
            sa.Column("video_url", sa.String(), nullable=False),
            sa.Column("segments", postgresql.JSONB(), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("video_url"),
        )


def downgrade() -> None:
    op.drop_table("video_transcript_cache")