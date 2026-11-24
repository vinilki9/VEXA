"""Append-only acceptance history. Do not alter past records on document updates."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid
from app.database import Base

class LegalAcceptance(Base):
    __tablename__ = "legal_acceptances"
    __table_args__ = (
        Index("ix_legal_acceptance_user_role", "user_id", "role"),
        UniqueConstraint("user_id", "role", "document_id", "version", "sha256", name="uq_legal_acceptance_revision"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    document_id: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    evidence_source: Mapped[str] = mapped_column(String(40), nullable=False)
