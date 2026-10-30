"""add_attempts_and_locked_until_to_inbound_events

Revision ID: 7761836f178f
Revises: f5ecd0dd63b2
Create Date: 2026-10-30 00:23:47.837227

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7761836f178f'
down_revision: Union[str, Sequence[str], None] = 'f5ecd0dd63b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "inbound_events",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "inbound_events",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    # Create index for efficient claiming of unprocessed, unlocked events
    op.create_index(
        "ix_inbound_events_claim",
        "inbound_events",
        ["processed", "locked_until"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_inbound_events_claim", table_name="inbound_events")
    op.drop_column("inbound_events", "locked_until")
    op.drop_column("inbound_events", "attempts")
