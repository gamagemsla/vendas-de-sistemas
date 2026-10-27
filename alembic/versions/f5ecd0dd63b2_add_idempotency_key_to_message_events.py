"""add idempotency_key to message_events

Revision ID: f5ecd0dd63b2
Revises: f1b4b7a8200f
Create Date: 2026-10-26 23:49:46.020370

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5ecd0dd63b2'
down_revision: Union[str, Sequence[str], None] = 'f1b4b7a8200f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "message_events",
        sa.Column("idempotency_key", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_message_events_idempotency_key",
        "message_events",
        ["idempotency_key"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_message_events_idempotency_key", table_name="message_events")
    op.drop_column("message_events", "idempotency_key")
