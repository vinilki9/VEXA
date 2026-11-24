"""Version-aware acceptance service. Use only after authenticating the actor."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.legal_documents import DOCS, validate_acceptances
from app.legal_acceptance_models import LegalAcceptance


def pending_documents(role: str, accepted_keys: set[tuple[str, str, str]]) -> list[dict]:
    return [{k: v for k, v in d.items() if k != "body"} for d in DOCS
            if d["role"] == role and d["required"]
            and (d["id"], d["version"], d["sha256"]) not in accepted_keys]


def accepted_keys_for(db: Session, user_id, role: str) -> set[tuple[str, str, str]]:
    rows = db.scalars(select(LegalAcceptance).where(
        LegalAcceptance.user_id == user_id, LegalAcceptance.role == role)).all()
    return {(r.document_id, r.version, r.sha256) for r in rows}


def record_acceptances(db: Session, user_id, role: str, acceptances: list[dict], evidence_source: str):
    # validate full set before any record is created
    verified = validate_acceptances(role, acceptances)
    already = accepted_keys_for(db, user_id, role)
    for item in verified:
        key = (item["id"], item["version"], item["sha256"])
        if key not in already:
            db.add(LegalAcceptance(user_id=user_id, role=role, document_id=item["id"],
                version=item["version"], sha256=item["sha256"], evidence_source=evidence_source))
            already.add(key)
    db.flush()
    return pending_documents(role, already)
