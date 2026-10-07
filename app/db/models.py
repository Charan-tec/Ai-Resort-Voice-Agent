from datetime import datetime, timezone, date
import uuid
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    Index,
    JSON,
    func,
    text
)
from sqlalchemy.dialects.postgresql import UUID, ExcludeConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


class Room(Base):
    __tablename__ = "rooms"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    room_type = Column(String(50), nullable=False)  # villa, suite, bungalow
    max_occupancy = Column(Integer, default=2, nullable=False)
    base_rate = Column(Float, nullable=False)
    amenities = Column(JSON, default=list, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    bookings = relationship("Booking", back_populates="room")

    @property
    def room_id(self) -> str:
        return self.id

    @property
    def base_rate_nightly(self) -> float:
        return self.base_rate


class Customer(Base):
    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(150), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    bookings = relationship("Booking", back_populates="customer")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_code = Column(String(50), unique=True, nullable=True, index=True)
    room_id = Column(String(50), ForeignKey("rooms.id"), nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)

    check_in = Column(Date, nullable=False)
    check_out = Column(Date, nullable=False)
    guests = Column(Integer, default=2, nullable=False)
    status = Column(String(30), default="pending", nullable=False)  # pending, confirmed, cancelled, expired
    total_price = Column(Float, nullable=False)
    currency = Column(String(10), default="USD", nullable=True)

    pending_token = Column(String(100), unique=True, nullable=True, index=True)
    hold_expires_at = Column(DateTime(timezone=True), nullable=True)
    add_ons = Column(JSON, default=list, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    room = relationship("Room", back_populates="bookings")
    customer = relationship("Customer", back_populates="bookings")

    # Authoritative Exclusion Constraint preventing overlapping bookings
    __table_args__ = (
        ExcludeConstraint(
            ("room_id", "="),
            (func.daterange(check_in, check_out, "[)"), "&&"),
            where=text("status IN ('pending', 'confirmed')"),
            using="gist",
            name="no_overlapping_bookings"
        ),
    )


class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_sid = Column(String(100), unique=True, nullable=False, index=True)
    caller_number = Column(String(50), nullable=True)
    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    status = Column(String(30), default="in-progress", nullable=False)
    barge_in_count = Column(Integer, default=0, nullable=False)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=True)
