"""003 add currency to bookings

Revision ID: 003_add_currency_to_bookings
Revises: 002_booking_details
Create Date: 2026-10-09 17:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_currency_to_bookings'
down_revision: Union[str, None] = '002_booking_details'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Safely and idempotently add currency column to bookings table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    has_column = False
    try:
        columns = [c['name'] for c in inspector.get_columns('bookings')]
        has_column = 'currency' in columns
    except Exception:
        has_column = False

    if not has_column:
        op.add_column(
            'bookings',
            sa.Column('currency', sa.String(length=10), nullable=True, server_default='USD')
        )


def downgrade() -> None:
    """Forward-only migration; column retained to prevent accidental data loss."""
    pass
