from app.legal_documents import DOCS
from app.legal_acceptance_service import pending_documents


def test_initial_pending_for_each_role():
    for role in ("client", "driver", "navigator", "dispatcher", "admin"):
        expected = {d["id"] for d in DOCS if d["role"] == role and d["required"]}
        assert {d["id"] for d in pending_documents(role, set())} == expected


def test_stored_version_requires_new_confirmation_after_revision():
    d = next(x for x in DOCS if x["role"] == "client" and x["required"])
    old = (d["id"], "previous-version", d["sha256"])
    assert d["id"] in {x["id"] for x in pending_documents("client", {old})}
    current = (d["id"], d["version"], d["sha256"])
    assert d["id"] not in {x["id"] for x in pending_documents("client", {current})}


def test_common_read_only_materials_do_not_require_acceptance():
    assert all(d["role"] == "client" for d in pending_documents("client", set()))


def test_marketing_does_not_block_registration():
    assert "marketing" not in {d["id"] for d in pending_documents("client", set())}
