"""session scoped webcam consent

Revision ID: a4b7c2d9e103
Revises: 9f2b64e8a6d1
Create Date: 2026-08-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a4b7c2d9e103"
down_revision: Union[str, Sequence[str], None] = "9f2b64e8a6d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "attention_logs" in tables:
        attention_columns = {c["name"] for c in inspector.get_columns("attention_logs")}
        if "session_id" not in attention_columns:
            op.add_column("attention_logs", sa.Column("session_id", sa.String(), nullable=True))
            op.create_index(op.f("ix_attention_logs_session_id"), "attention_logs", ["session_id"], unique=False)

    if "consent" not in tables:
        return

    consent_columns = {c["name"] for c in inspector.get_columns("consent")}
    if "session_id" not in consent_columns:
        op.add_column("consent", sa.Column("session_id", sa.String(), nullable=True))
        op.execute("UPDATE consent SET session_id = 'legacy' WHERE session_id IS NULL")
        op.alter_column("consent", "session_id", nullable=False)

    pk = inspector.get_pk_constraint("consent")
    pk_name = pk.get("name")
    constrained = set(pk.get("constrained_columns") or [])
    if constrained != {"student_id", "session_id"}:
        if pk_name:
            op.drop_constraint(pk_name, "consent", type_="primary")
        op.create_primary_key("pk_consent", "consent", ["student_id", "session_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "consent" in tables:
        pk = inspector.get_pk_constraint("consent")
        pk_name = pk.get("name")
        constrained = set(pk.get("constrained_columns") or [])
        if constrained != {"student_id"}:
            if pk_name:
                op.drop_constraint(pk_name, "consent", type_="primary")
            op.create_primary_key("pk_consent", "consent", ["student_id"])
        columns = {c["name"] for c in sa.inspect(conn).get_columns("consent")}
        if "session_id" in columns:
            op.drop_column("consent", "session_id")

    if "attention_logs" in tables:
        indexes = {idx["name"] for idx in inspector.get_indexes("attention_logs")}
        if "ix_attention_logs_session_id" in indexes:
            op.drop_index("ix_attention_logs_session_id", table_name="attention_logs")
        columns = {c["name"] for c in sa.inspect(conn).get_columns("attention_logs")}
        if "session_id" in columns:
            op.drop_column("attention_logs", "session_id")
