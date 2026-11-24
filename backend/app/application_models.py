
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# APPLICATION STATUSES
# new             — новая заявка
# reviewing       — на рассмотрении
# needs_info      — требуются уточнения
# approved        — одобрена
# rejected        — отклонена
# ============================================================

APPLICATION_STATUS_CHECK = (
    "status IN ('new', 'reviewing', 'needs_info', 'approved', 'rejected')"
)


# ============================================================
# DISPATCHER APPLICATIONS
# Заявки на подключение диспетчеров к платформе VEXA.
# Создание учётной записи и выдача прав выполняются отдельно,
# только после решения главного администратора.
# ============================================================

class DispatcherApplication(Base):
    __tablename__ = "dispatcher_applications"

    __table_args__ = (
        CheckConstraint(
            APPLICATION_STATUS_CHECK,
            name="dispatcher_applications_status_valid",
        ),
        Index(
            "ix_dispatcher_applications_status_created",
            "status",
            "created_at",
        ),
        Index(
            "ix_dispatcher_applications_phone_status",
            "phone",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )

    # Если заявка отправлена авторизованным пользователем,
    # сохраняем связь с его существующей учётной записью.
    applicant_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    phone: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    email: Mapped[str | None] = mapped_column(
        String(254),
        nullable=True,
    )

    # Города, в которых заявитель хочет работать.
    # Здесь хранятся коды или названия городов,
    # окончательные разрешения выдаются администратором.
    requested_cities: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    experience: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    applicant_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="new",
        index=True,
    )

    admin_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Пользователь, который будет связан с заявкой
    # после одобрения и отдельного создания/назначения доступа.
    approved_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
        nullable=False,
    )


# ============================================================
# PARTNER APPLICATIONS
# Заявки владельцев таксопарков на подключение к VEXA.
# Организация создаётся и активируется только после одобрения.
# ============================================================

class PartnerApplication(Base):
    __tablename__ = "partner_applications"

    __table_args__ = (
        CheckConstraint(
            APPLICATION_STATUS_CHECK,
            name="partner_applications_status_valid",
        ),
        Index(
            "ix_partner_applications_status_created",
            "status",
            "created_at",
        ),
        Index(
            "ix_partner_applications_phone_status",
            "phone",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )

    applicant_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    contact_full_name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    phone: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    email: Mapped[str | None] = mapped_column(
        String(254),
        nullable=True,
    )

    organization_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    legal_name: Mapped[str | None] = mapped_column(
        String(250),
        nullable=True,
    )

    tax_identifier: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # Запрашиваемые города. Это пожелание заявителя,
    # а не автоматически выданные права на работу.
    requested_cities: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    fleet_size: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    applicant_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="new",
        index=True,
    )

    admin_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Заполняется после одобрения и создания организации.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
        nullable=False,
    )
