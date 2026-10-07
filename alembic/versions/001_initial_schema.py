"""001 initial schema and exclusion constraint

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-16 16:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable btree_gist extension
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")

    # 2. Create rooms table
    op.create_table(
        'rooms',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('room_type', sa.String(length=50), nullable=False),
        sa.Column('max_occupancy', sa.Integer(), nullable=False),
        sa.Column('base_rate', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. Create customers table
    op.create_table(
        'customers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('full_name', sa.String(length=150), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customers_email'), 'customers', ['email'], unique=False)

    # 4. Create bookings table
    op.create_table(
        'bookings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('booking_code', sa.String(length=50), nullable=True),
        sa.Column('room_id', sa.String(length=50), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('check_in', sa.Date(), nullable=False),
        sa.Column('check_out', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('total_price', sa.Float(), nullable=False),
        sa.Column('pending_token', sa.String(length=100), nullable=True),
        sa.Column('hold_expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bookings_booking_code'), 'bookings', ['booking_code'], unique=True)
    op.create_index(op.f('ix_bookings_pending_token'), 'bookings', ['pending_token'], unique=True)
    op.create_index(op.f('ix_bookings_room_id'), 'bookings', ['room_id'], unique=False)

    # 5. Create exclusion constraint using btree_gist
    op.execute("""
        ALTER TABLE bookings ADD CONSTRAINT no_overlapping_bookings
        EXCLUDE USING gist (
            room_id WITH =,
            daterange(check_in, check_out, '[)') WITH &&
        )
        WHERE (status IN ('pending', 'confirmed'));
    """)

    # 6. Create call_logs table
    op.create_table(
        'call_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('call_sid', sa.String(length=100), nullable=False),
        sa.Column('caller_number', sa.String(length=50), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('barge_in_count', sa.Integer(), nullable=False),
        sa.Column('booking_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_call_logs_call_sid'), 'call_logs', ['call_sid'], unique=True)


def downgrade() -> None:
    op.drop_table('call_logs')
    op.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS no_overlapping_bookings;")
    op.drop_table('bookings')
    op.drop_table('customers')
    op.drop_table('rooms')
