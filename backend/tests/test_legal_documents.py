import hashlib
import pytest
from app.legal_documents import DOCS, ROLES, validate_acceptances

@pytest.mark.parametrize("role", sorted(ROLES))
def test_each_role_has_required_documents(role):
    assert any(d["required"] for d in DOCS if d["role"] == role)

def test_documents_hashes_valid():
    assert all(hashlib.sha256(d["body"].encode()).hexdigest() == d["sha256"] for d in DOCS)

def test_client_required():
    with pytest.raises(ValueError): validate_acceptances("client", [])

def test_optional_marketing_not_required():
    x = [d for d in DOCS if d["role"] == "client" and d["required"]]
    accepted = [{"id": d["id"], "sha256":d["sha256"], "version":d["version"], "accepted":True} for d in x]
    assert len(validate_acceptances("client", accepted)) == len(x)

def test_version_tampering_rejected():
    x = next(d for d in DOCS if d["role"] == "client" and d["required"])
    with pytest.raises(ValueError): validate_acceptances("client", [{"id":x["id"],"version":"invalid","sha256":x["sha256"],"accepted":True}])

def test_duplicate_rejected():
    x = next(d for d in DOCS if d["role"] == "client" and d["required"])
    rec={"id":x["id"],"version":x["version"],"sha256":x["sha256"],"accepted":True}
    with pytest.raises(ValueError): validate_acceptances("client", [rec,rec])


def test_common_reference_visible_to_each_role():
    from app.legal_documents import list_documents, document_text
    for role in ROLES:
        docs = list_documents(role)
        refs = [d for d in docs if d["role"] == "common"]
        assert len(refs) == 6
        assert all(d["required"] is False and "body" not in d for d in refs)
        assert "Законодательство" in document_text(role, refs[0]["id"])["body"]

def test_common_reference_cannot_be_submitted_as_consent():
    doc = next(d for d in DOCS if d["role"] == "common")
    with pytest.raises(ValueError, match="Unknown document"):
        validate_acceptances("client", [{"id":doc["id"],"version":doc["version"],"sha256":doc["sha256"],"accepted":True}])

def test_no_common_doc_marked_required():
    assert all(not d["required"] for d in DOCS if d["role"] == "common")
