"""002 add amenities to rooms and guests, add_ons to bookings

Revision ID: 002_booking_details
Revises: 001_initial_schema
Create Date: 2026-09-22 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_booking_details'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rooms', sa.Column('amenities', sa.JSON(), nullable=True))
    op.add_column('bookings', sa.Column('guests', sa.Integer(), nullable=False, server_default='2'))
    op.add_column('bookings', sa.Column('add_ons', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('bookings', 'add_ons')
    op.drop_column('bookings', 'guests')
    op.drop_column('rooms', 'amenities')
