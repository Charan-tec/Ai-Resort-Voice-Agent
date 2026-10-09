import importlib.util
import os
import pytest
import sqlalchemy as sa
from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.db.models import Booking


def test_booking_model_currency_attributes():
    """Verify Booking SQLAlchemy model has currency column with expected properties."""
    assert "currency" in Booking.__table__.columns
    col = Booking.__table__.columns["currency"]
    assert isinstance(col.type, sa.String)
    assert col.type.length == 10
    assert col.nullable is True
    assert col.default.arg == "USD"


def test_migration_revision_chain():
    """Verify 003_add_currency_to_bookings revision connects to 002_booking_details."""
    mig_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "alembic", "versions", "003_add_currency_to_bookings.py")
    )
    assert os.path.exists(mig_path), f"Migration file not found at {mig_path}"

    spec = importlib.util.spec_from_file_location("mig_003", mig_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.revision == "003_add_currency_to_bookings"
    assert mod.down_revision == "002_booking_details"
    assert callable(mod.upgrade)
    assert callable(mod.downgrade)


def test_migration_execution_and_idempotency():
    """Verify migration upgrade adds column, is idempotent, and downgrade is safe."""
    mig_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "alembic", "versions", "003_add_currency_to_bookings.py")
    )
    spec = importlib.util.spec_from_file_location("mig_003", mig_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    engine = sa.create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(sa.text("CREATE TABLE bookings (id VARCHAR(50) PRIMARY KEY, total_price FLOAT);"))
        conn.commit()

        # Check initial state
        insp = sa.inspect(conn)
        cols_initial = [c["name"] for c in insp.get_columns("bookings")]
        assert "currency" not in cols_initial

        # Run upgrade
        ctx = MigrationContext.configure(conn)
        op._proxy = Operations(ctx)
        mod.upgrade()
        conn.commit()

        # Check column was added
        insp_after = sa.inspect(conn)
        cols_after = [c["name"] for c in insp_after.get_columns("bookings")]
        assert "currency" in cols_after

        # Re-run upgrade to verify idempotency (must not raise duplicate column error)
        mod.upgrade()
        conn.commit()

        # Verify forward-only downgrade safety (must not drop column or fail)
        mod.downgrade()
        conn.commit()
        insp_downgrade = sa.inspect(conn)
        cols_downgrade = [c["name"] for c in insp_downgrade.get_columns("bookings")]
        assert "currency" in cols_downgrade
