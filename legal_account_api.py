"""Authenticated legal history and updated terms acceptance.

Navigator without authenticated accounts uses local UI state; it must not issue
server-side evidence claiming an identity that was never verified.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.legal_acceptance_models import LegalAcceptance
from app.legal_acceptance_service import accepted_keys_for, pending_documents, record_acceptances
from app.security import get_current_passenger, get_current_driver, get_current_dispatcher
from app.platform_admin_auth import get_current_platform_admin

router = APIRouter(prefix="/api/v1/legal/account", tags=["Legal acceptance history"])

class AcceptRequest(BaseModel):
    selections: list[dict] = Field(default_factory=list)

ROLES = {
    "client": get_current_passenger,
    "driver": get_current_driver,
    "dispatcher": get_current_dispatcher,
    "admin": get_current_platform_admin,
}

# Explicit per-role routes make auth dependencies visible in OpenAPI and prevent role spoofing.
def add_role_routes(role, dependency):
    @router.get(f"/{role}/pending", name=f"legal_pending_{role}")
    def pending(user=Depends(dependency), db: Session = Depends(get_db)):
        return {"role": role, "pending": pending_documents(role, accepted_keys_for(db, user.id, role))}

    @router.get(f"/{role}/history", name=f"legal_history_{role}")
    def history(user=Depends(dependency), db: Session = Depends(get_db)):
        records = db.scalars(select(LegalAcceptance).where(
            LegalAcceptance.user_id == user.id, LegalAcceptance.role == role)
            .order_by(LegalAcceptance.accepted_at.desc())).all()
        return [{"document_id": r.document_id, "version": r.version,
                 "sha256": r.sha256, "accepted_at": r.accepted_at,
                 "evidence_source": r.evidence_source} for r in records]

    @router.post(f"/{role}/accept", name=f"legal_accept_{role}")
    def accept(payload: AcceptRequest, user=Depends(dependency), db: Session = Depends(get_db)):
        try:
            missing = record_acceptances(db, user.id, role, payload.selections, "authenticated_account")
            db.commit()
        except ValueError as exc:
            db.rollback()
            raise HTTPException(422, str(exc)) from exc
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(409, "Повторный запрос; обновите статус документов") from exc
        return {"accepted": True, "pending": missing}

for _role, _dependency in ROLES.items():
    add_role_routes(_role, _dependency)
