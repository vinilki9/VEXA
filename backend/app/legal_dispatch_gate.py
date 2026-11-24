"""Fail-closed server-side eligibility gate for dispatch paths.

This reads externally verified snapshots. It does NOT check government registries.
The operational integration must separately establish a trusted verification workflow.
"""
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings
from app.legal_compliance import DispatchEligibility, evaluate_dispatch_eligibility
from app.legal_dispatch_models import LegalDispatchVerification


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def legal_eligibility(db: Session, driver_user_id, vehicle_id, *, child_seats_required=False, now=None) -> tuple[bool, tuple[str, ...]]:
    if not settings.legal_dispatch_enforcement:
        return True, ()  # Only permitted in NON-production development.
    now = _utc(now or datetime.now(timezone.utc))
    record = db.scalar(select(LegalDispatchVerification).where(
        LegalDispatchVerification.driver_user_id == driver_user_id,
        LegalDispatchVerification.vehicle_id == vehicle_id,
        LegalDispatchVerification.checked_at <= now,
        LegalDispatchVerification.valid_until > now,
    ).order_by(LegalDispatchVerification.checked_at.desc(), LegalDispatchVerification.id.desc()).limit(1))
    if record is None:
        return False, ("verification_missing_or_expired",)
    # Defensive re-check even if the repository query is mocked/cached.
    if _utc(record.checked_at) > now or _utc(record.valid_until) <= now:
        return False, ("verification_missing_or_expired",)
    if not (record.source_reference.strip() and record.verified_by.strip()):
        return False, ("verification_source_missing",)
    ready = DispatchEligibility(**{
        name: bool(getattr(record,name)) for name in (
            "carrier_registry_confirmed", "carrier_permission_active", "vehicle_registry_confirmed",
            "vehicle_registered_to_carrier", "driver_qualified", "driver_shift_compliant",
            "waybill_compliant", "insurance_verified", "carrier_identity_ready_for_passenger",
            "child_seats_compliant"
        )}, verification_fresh=True)
    return evaluate_dispatch_eligibility(ready, child_seats_required=child_seats_required)
