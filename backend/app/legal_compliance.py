"""VEXA legal compliance primitives (draft, not a substitute for licensed legal review).

No permissive fallback: unknown verification means NOT READY for dispatch.
The dispatch API MUST separately integrate these checks before production use.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Literal


def canonical_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def document_hash(document_bytes: bytes) -> str:
    return sha256(document_bytes).hexdigest()


@dataclass(frozen=True)
class LegalDocument:
    doc_type: str
    version: str
    sha256_hex: str
    published_at: str


@dataclass(frozen=True)
class ConsentDecision:
    subject_id: str
    document: LegalDocument
    purpose: str
    accepted: bool
    recorded_at: str
    channel: str
    correlation_id: str

    def evidence_payload(self) -> dict:
        if not self.subject_id or not self.document.doc_type or not self.document.version:
            raise ValueError("Missing subject or document identifiers")
        if not self.purpose or not self.correlation_id:
            raise ValueError("Purpose and correlation ID required")
        if self.channel not in {"client_android", "driver_android", "navigator_android", "web"}:
            raise ValueError("Unknown evidence channel")
        if len(self.document.sha256_hex) != 64 or any(c not in '0123456789abcdef' for c in self.document.sha256_hex):
            raise ValueError("Invalid document sha256")
        return {
            "subject_id": self.subject_id,
            "document_type": self.document.doc_type,
            "document_version": self.document.version,
            "document_sha256": self.document.sha256_hex,
            "purpose": self.purpose,
            "accepted": self.accepted,
            "recorded_at": self.recorded_at,
            "channel": self.channel,
            "correlation_id": self.correlation_id,
        }


def chain_event(previous_hash: str, event: dict) -> str:
    """Tamper-evident linking only. NOT proof against rewriting the entire DB.

    Production must use protected append-only storage, external anchors and audited keys.
    """
    if len(previous_hash) != 64 or any(ch not in '0123456789abcdef' for ch in previous_hash):
        raise ValueError("Invalid previous hash")
    return sha256((previous_hash + '\n' + canonical_json(event)).encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class DispatchEligibility:
    carrier_registry_confirmed: bool
    carrier_permission_active: bool
    vehicle_registry_confirmed: bool
    vehicle_registered_to_carrier: bool
    driver_qualified: bool
    driver_shift_compliant: bool
    waybill_compliant: bool
    insurance_verified: bool
    carrier_identity_ready_for_passenger: bool
    verification_fresh: bool
    child_seats_compliant: bool = True


def evaluate_dispatch_eligibility(e: DispatchEligibility, *, child_seats_required: bool = False) -> tuple[bool, tuple[str, ...]]:
    checks = {
        "carrier_registry_unconfirmed": e.carrier_registry_confirmed,
        "carrier_permission_inactive": e.carrier_permission_active,
        "vehicle_registry_unconfirmed": e.vehicle_registry_confirmed,
        "vehicle_carrier_mismatch": e.vehicle_registered_to_carrier,
        "driver_not_qualified": e.driver_qualified,
        "shift_limits_exceeded_or_unknown": e.driver_shift_compliant,
        "waybill_missing_or_invalid": e.waybill_compliant,
        "insurance_unverified": e.insurance_verified,
        "carrier_identity_not_disclosable": e.carrier_identity_ready_for_passenger,
        "verification_stale": e.verification_fresh,
    }
    if child_seats_required:
        checks["child_restraint_unavailable"] = e.child_seats_compliant
    blockers = tuple(name for name, passed in checks.items() if not passed)
    return not blockers, blockers
