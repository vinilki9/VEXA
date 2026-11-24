"""Verified external-document snapshot, scoped to driver+vehicle. Not registry verification by itself."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class LegalDispatchVerification(Base):
    __tablename__ = "legal_dispatch_verifications"
    __table_args__ = (Index("ix_legal_verification_driver_vehicle", "driver_user_id", "vehicle_id"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    driver_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    verified_by: Mapped[str] = mapped_column(String(120), nullable=False)
    carrier_registry_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    carrier_permission_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    vehicle_registry_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    vehicle_registered_to_carrier: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    driver_qualified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    driver_shift_compliant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    waybill_compliant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    insurance_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    carrier_identity_ready_for_passenger: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    child_seats_compliant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
