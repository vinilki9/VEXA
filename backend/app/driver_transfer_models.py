
import uuid

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models import now_utc


class DriverBranchTransfer(Base):
    """
    Неизменяемая история переводов водителя между филиалами
    и городами.

    Общий долг водителя сохраняется при переводе.
    Исторические финансовые операции не изменяются.
    """

    __tablename__ = "driver_branch_transfers"

    __table_args__ = (
        CheckConstraint(
            "debt_kopecks_at_transfer >= 0",
            name="driver_branch_transfers_debt_nonnegative",
        ),
        CheckConstraint(
            """
            from_branch_id IS NULL
            OR to_branch_id IS NULL
            OR from_branch_id != to_branch_id
            """,
            name="driver_branch_transfers_different_branches",
        ),
        Index(
            "ix_driver_branch_transfers_driver_created",
            "driver_user_id",
            "created_at",
        ),
        Index(
            "ix_driver_branch_transfers_from_city_created",
            "from_city_id",
            "created_at",
        ),
        Index(
            "ix_driver_branch_transfers_to_city_created",
            "to_city_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    driver_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "driver_profiles.user_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    from_city_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "cities.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    to_city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "cities.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    from_branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "branches.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    to_branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "branches.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    debt_kopecks_at_transfer: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    transferred_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )
