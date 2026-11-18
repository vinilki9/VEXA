
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.driver_transfer_models import DriverBranchTransfer
from app.models import (
    Branch,
    City,
    DispatcherProfile,
    DriverProfile,
    DriverWallet,
    User,
)
from app.security import get_current_dispatcher


router = APIRouter(
    prefix="/api/v1/dispatch",
    tags=["Driver Transfers"],
)


class DriverTransferRequest(BaseModel):
    to_city_id: UUID
    to_branch_id: UUID


def require_chief_dispatcher(
    db: Session,
    dispatcher: User,
) -> DispatcherProfile:
    profile = db.get(
        DispatcherProfile,
        dispatcher.id,
    )

    if (
        profile is None
        or not profile.is_active
        or profile.role != "chief_dispatcher"
    ):
        raise HTTPException(
            status_code=403,
            detail="Переводить водителей может только главный диспетчер",
        )

    return profile


@router.post("/drivers/{driver_user_id}/transfer")
def transfer_driver(
    driver_user_id: UUID,
    payload: DriverTransferRequest,
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    """
    Перевод водителя между филиалами и городами.

    Баланс и резерв кошелька сохраняются.
    Отрицательный баланс продолжает отражать долг VEXA.
    Привязка кошелька обновляется вместе с профилем водителя.
    Исторические финансовые операции не изменяются.
    Перевод записывается отдельной неизменяемой операцией.
    """

    require_chief_dispatcher(
        db,
        dispatcher,
    )

    driver_profile = db.scalar(
        select(DriverProfile)
        .where(
            DriverProfile.user_id == driver_user_id,
            DriverProfile.is_active.is_(True),
        )
        .with_for_update()
    )

    if driver_profile is None:
        raise HTTPException(
            status_code=404,
            detail="Активный водитель не найден",
        )

    driver_user = db.get(
        User,
        driver_user_id,
    )

    if driver_user is None or not driver_user.is_active:
        raise HTTPException(
            status_code=404,
            detail="Учётная запись водителя недоступна",
        )

    target_city = db.get(
        City,
        payload.to_city_id,
    )

    if target_city is None or not target_city.is_active:
        raise HTTPException(
            status_code=404,
            detail="Целевой город не найден или неактивен",
        )

    target_branch = db.get(
        Branch,
        payload.to_branch_id,
    )

    if (
        target_branch is None
        or not target_branch.is_active
        or target_branch.city_id != target_city.id
    ):
        raise HTTPException(
            status_code=422,
            detail="Целевой филиал не принадлежит выбранному городу или неактивен",
        )

    from_city_id = driver_profile.city_id
    from_branch_id = driver_profile.branch_id

    if (
        from_city_id == target_city.id
        and from_branch_id == target_branch.id
    ):
        raise HTTPException(
            status_code=409,
            detail="Водитель уже числится в выбранном филиале",
        )

    wallet = db.scalar(
        select(DriverWallet)
        .where(
            DriverWallet.driver_user_id == driver_user_id,
        )
        .with_for_update()
    )

    if wallet is None:
        wallet = DriverWallet(
            driver_user_id=driver_user_id,
            city_id=from_city_id,
            branch_id=from_branch_id,
            balance_kopecks=0,
            reserved_kopecks=0,
        )
        db.add(wallet)

    # Долг определяется исключительно по текущему балансу кошелька.
    # Отрицательный баланс не обнуляется и не переносится отдельной операцией.
    current_balance = int(wallet.balance_kopecks or 0)
    current_reserved = int(wallet.reserved_kopecks or 0)
    debt_kopecks = max(-current_balance, 0)

    transfer = DriverBranchTransfer(
        driver_user_id=driver_user_id,
        from_city_id=from_city_id,
        to_city_id=target_city.id,
        from_branch_id=from_branch_id,
        to_branch_id=target_branch.id,
        debt_kopecks_at_transfer=debt_kopecks,
        transferred_by_user_id=dispatcher.id,
    )

    # Меняем только географическую привязку.
    # Баланс и зарезервированные средства остаются без изменений.
    driver_profile.city_id = target_city.id
    driver_profile.branch_id = target_branch.id

    wallet.city_id = target_city.id
    wallet.branch_id = target_branch.id
    wallet.balance_kopecks = current_balance
    wallet.reserved_kopecks = current_reserved

    db.add(transfer)

    try:
        db.commit()
        db.refresh(transfer)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Не удалось сохранить перевод. Проверьте данные и повторите операцию.",
        )

    return {
        "success": True,
        "message": "Водитель успешно переведён",
        "transfer": {
            "id": str(transfer.id),
            "driver_user_id": str(driver_user_id),
            "from_city_id": str(from_city_id),
            "to_city_id": str(target_city.id),
            "from_branch_id": (
                str(from_branch_id)
                if from_branch_id is not None
                else None
            ),
            "to_branch_id": str(target_branch.id),
            "debt_kopecks_at_transfer": debt_kopecks,
            "debt_rub_at_transfer": round(
                debt_kopecks / 100,
                2,
            ),
            "transferred_by_user_id": str(dispatcher.id),
            "created_at": transfer.created_at,
        },
    }
