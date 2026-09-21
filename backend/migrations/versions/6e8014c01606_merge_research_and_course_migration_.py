"""merge research and course migration heads

Revision ID: 6e8014c01606
Revises: c1d5e7f9a203, d2e4f6a8b901
Create Date: 2026-08-29 15:17:41.940269

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6e8014c01606'
down_revision: Union[str, Sequence[str], None] = ('c1d5e7f9a203', 'd2e4f6a8b901')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
