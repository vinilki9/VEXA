import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.legal_compliance import (
    LegalDocument, ConsentDecision, DispatchEligibility,
    document_hash, chain_event, evaluate_dispatch_eligibility,
)

class LegalComplianceTests(unittest.TestCase):
    def test_document_hash_changes(self):
        self.assertNotEqual(document_hash(b"v1"), document_hash(b"v2"))

    def test_consent_evidence_version_bound(self):
        doc = LegalDocument("personal_data", "2026-11-22", document_hash(b"version1"), "2026-11-22T00:00:00Z")
        e = ConsentDecision("anonymous-user-id", doc, "marketing", False, "2026-11-22T00:01:00Z", "client_android", "sample-id")
        self.assertFalse(e.evidence_payload()["accepted"])
        self.assertEqual(e.evidence_payload()["document_sha256"], doc.sha256_hex)

    def test_chain_is_deterministic_and_tamper_evident(self):
        zero = "0" * 64
        e = {"action": "consent", "accepted": False}
        self.assertEqual(chain_event(zero,e), chain_event(zero,e))
        self.assertNotEqual(chain_event(zero,e), chain_event(zero,{**e,"accepted":True}))

    def test_dispatch_fail_closed(self):
        e = DispatchEligibility(*(False,)*10)
        allowed, blockers = evaluate_dispatch_eligibility(e)
        self.assertFalse(allowed)
        self.assertGreaterEqual(len(blockers), 8)

    def test_dispatch_valid_fixture(self):
        e = DispatchEligibility(*(True,)*10)
        self.assertEqual(evaluate_dispatch_eligibility(e), (True, ()))

    def test_child_seat_gate(self):
        e = DispatchEligibility(*(True,)*10, child_seats_compliant=False)
        self.assertTrue(evaluate_dispatch_eligibility(e)[0])
        self.assertFalse(evaluate_dispatch_eligibility(e, child_seats_required=True)[0])

    def test_reject_invalid_hash(self):
        e = ConsentDecision('u', LegalDocument('policy','v1','invalid','now'), 'analytics',True,'now','web','c')
        with self.assertRaises(ValueError): e.evidence_payload()

if __name__=='__main__': unittest.main()
