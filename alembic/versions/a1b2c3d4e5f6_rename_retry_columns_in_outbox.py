"""rename retry columns in outbox

Revision ID: a1b2c3d4e5f6
Revises: 7761836f178f
Create Date: 2026-10-31 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str = '7761836f178f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('outbox', 'retry_count', new_column_name='attempts')
    op.alter_column('outbox', 'max_retries', new_column_name='max_attempts')


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('outbox', 'attempts', new_column_name='retry_count')
    op.alter_column('outbox', 'max_attempts', new_column_name='max_retries')