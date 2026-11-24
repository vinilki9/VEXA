"""Isolated deterministic gate tests: no official registries are queried."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch
from app.legal_dispatch_gate import legal_eligibility

class DummyDB:
    def __init__(self, record): self.record = record
    def scalar(self, stmt): return self.record

FIELDS = ("carrier_registry_confirmed", "carrier_permission_active", "vehicle_registry_confirmed",
    "vehicle_registered_to_carrier", "driver_qualified", "driver_shift_compliant",
    "waybill_compliant", "insurance_verified", "carrier_identity_ready_for_passenger", "child_seats_compliant")

def record(now, **overrides):
    d = dict(checked_at=now-timedelta(hours=1), valid_until=now+timedelta(hours=1),
        source_reference="registry:example-record", verified_by="trained-operator")
    d.update({field: True for field in FIELDS})
    d.update(overrides)
    return SimpleNamespace(**d)

def check(row, child=False):
    now = datetime(2026,11,22,tzinfo=timezone.utc)
    with patch('app.legal_dispatch_gate.settings.legal_dispatch_enforcement', True):
        return legal_eligibility(DummyDB(row), uuid4(), uuid4(), now=now, child_seats_required=child)

def test_missing_fails_closed():
    assert check(None)[0] is False

def test_valid_passes():
    assert check(record(datetime(2026,11,22,tzinfo=timezone.utc)))[0] is True

def test_missing_insurance_blocks():
    assert 'insurance_unverified' in check(record(datetime(2026,11,22,tzinfo=timezone.utc), insurance_verified=False))[1]

def test_invalid_source_blocks():
    assert 'verification_source_missing' in check(record(datetime(2026,11,22,tzinfo=timezone.utc), source_reference=''))[1]

def test_child_seat_blocks_child_order_only():
    r=record(datetime(2026,11,22,tzinfo=timezone.utc),child_seats_compliant=False)
    assert check(r,child=True)[0] is False
    assert check(r,child=False)[0] is True

def test_expired_record_blocks():
    now=datetime(2026,11,22,tzinfo=timezone.utc)
    assert 'verification_missing_or_expired' in check(record(now, valid_until=now-timedelta(seconds=1)))[1]

def test_future_verification_blocks():
    now=datetime(2026,11,22,tzinfo=timezone.utc)
    assert check(record(now, checked_at=now+timedelta(hours=1)))[0] is False
