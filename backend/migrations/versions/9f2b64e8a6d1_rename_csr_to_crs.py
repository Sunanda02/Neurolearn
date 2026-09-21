"""rename csr history to crs

Revision ID: 9f2b64e8a6d1
Revises: c36c8bab1754
Create Date: 2026-08-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "9f2b64e8a6d1"
down_revision: Union[str, Sequence[str], None] = "c36c8bab1754"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "csr_history" in tables and "crs_history" not in tables:
        op.rename_table("csr_history", "crs_history")
        op.execute("ALTER INDEX IF EXISTS ix_csr_history_student_id RENAME TO ix_crs_history_student_id")

    tables = set(sa.inspect(conn).get_table_names())
    if "crs_history" in tables:
        columns = {c["name"] for c in sa.inspect(conn).get_columns("crs_history")}
        if "attention" in columns and "behavioral_cue" not in columns:
            op.alter_column("crs_history", "attention", new_column_name="behavioral_cue")
        if "csr" in columns and "crs" not in columns:
            op.alter_column("crs_history", "csr", new_column_name="crs")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "crs_history" in tables:
        columns = {c["name"] for c in inspector.get_columns("crs_history")}
        if "behavioral_cue" in columns and "attention" not in columns:
            op.alter_column("crs_history", "behavioral_cue", new_column_name="attention")
        if "crs" in columns and "csr" not in columns:
            op.alter_column("crs_history", "crs", new_column_name="csr")

    tables = set(sa.inspect(conn).get_table_names())
    if "crs_history" in tables and "csr_history" not in tables:
        op.rename_table("crs_history", "csr_history")
        op.execute("ALTER INDEX IF EXISTS ix_crs_history_student_id RENAME TO ix_csr_history_student_id")
