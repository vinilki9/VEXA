from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.models import (
    Branch,
    City,
    DispatcherProfile,
    DriverFinanceTransaction,
    DriverLocation,
    DriverProfile,
    User,
)
from app.security import get_current_dispatcher


router = APIRouter(
    prefix="/api/v1/dispatch",
    tags=["Dispatcher Drivers"],
)


def get_dispatcher_profile(
    db: Session,
    dispatcher: User,
) -> DispatcherProfile:
    profile = db.get(
        DispatcherProfile,
        dispatcher.id,
    )

    if profile is None or not profile.is_active:
        raise HTTPException(
            403,
            "Доступ диспетчера запрещён",
        )

    if profile.role == "dispatcher":
        if profile.branch_id is None:
            raise HTTPException(
                403,
                "Диспетчер не привязан к филиалу",
            )

        branch = db.get(
            Branch,
            profile.branch_id,
        )

        if branch is None or not branch.is_active:
            raise HTTPException(
                403,
                "Филиал диспетчера недоступен",
            )

    elif profile.role != "chief_dispatcher":
        raise HTTPException(
            403,
            "Неизвестная роль диспетчера",
        )

    return profile


@router.get("/drivers/locations")
def list_driver_locations(
    city_code: str = "obolensk",
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    profile = get_dispatcher_profile(
        db,
        dispatcher,
    )

    branch = None

    if profile.role == "dispatcher":
        branch = db.get(
            Branch,
            profile.branch_id,
        )

        if branch is None or not branch.is_active:
            raise HTTPException(
                403,
                "Филиал диспетчера недоступен",
            )

        city = db.get(
            City,
            branch.city_id,
        )

        if city is None or not city.is_active:
            raise HTTPException(
                403,
                "Город филиала недоступен",
            )

    else:
        city = db.scalar(
            select(City).where(
                City.code == city_code,
                City.is_active.is_(True),
            )
        )

        if city is None:
            raise HTTPException(
                404,
                "Город не найден или неактивен",
            )

    query = (
        select(
            DriverProfile,
            User,
            DriverLocation,
            City,
            Branch,
        )
        .join(
            User,
            User.id == DriverProfile.user_id,
        )
        .join(
            City,
            City.id == DriverProfile.city_id,
        )
        .outerjoin(
            DriverLocation,
            DriverLocation.driver_user_id
            == DriverProfile.user_id,
        )
        .outerjoin(
            Branch,
            Branch.id == DriverProfile.branch_id,
        )
        .where(
            DriverProfile.city_id == city.id,
            DriverProfile.is_active.is_(True),
            User.is_active.is_(True),
            City.is_active.is_(True),
        )
    )

    if profile.role == "dispatcher":
        query = query.where(
            DriverProfile.branch_id == profile.branch_id,
        )

    rows = db.execute(
        query.order_by(
            DriverProfile.is_online.desc(),
            User.username,
        )
    ).all()

    drivers = []

    for driver_profile, user, location, driver_city, driver_branch in rows:
        drivers.append(
            {
                "user_id": str(user.id),
                "username": user.username,
                "phone": user.phone,
                "city": {
                    "id": str(driver_city.id),
                    "code": driver_city.code,
                    "name": driver_city.name,
                },
                "branch": (
                    {
                        "id": str(driver_branch.id),
                        "name": driver_branch.name,
                    }
                    if driver_branch is not None
                    else None
                ),
                "is_online": driver_profile.is_online,
                "rating": str(driver_profile.rating),
                "location": (
                    {
                        "latitude": location.latitude,
                        "longitude": location.longitude,
                        "accuracy_meters": (
                            location.accuracy_meters
                        ),
                        "recorded_at": location.recorded_at,
                        "updated_at": location.updated_at,
                    }
                    if location is not None
                    else None
                ),
            }
        )

    return {
        "city_code": city.code,
        "drivers_count": len(drivers),
        "drivers": drivers,
    }


@router.get("/drivers/finance")
def list_driver_finance(
    city_code: str = "obolensk",
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    profile = get_dispatcher_profile(
        db,
        dispatcher,
    )

    if profile.role == "dispatcher":
        branch = db.get(
            Branch,
            profile.branch_id,
        )

        if branch is None or not branch.is_active:
            raise HTTPException(
                403,
                "Филиал диспетчера недоступен",
            )

        city = db.get(
            City,
            branch.city_id,
        )

        if city is None or not city.is_active:
            raise HTTPException(
                403,
                "Город филиала недоступен",
            )
    else:
        city = db.scalar(
            select(City).where(
                City.code == city_code,
                City.is_active.is_(True),
            )
        )

        if city is None:
            raise HTTPException(
                404,
                "Город не найден или неактивен",
            )

    query = (
        select(
            DriverProfile.user_id,
            User.username,
            User.phone,
            DriverProfile.rating,
            DriverProfile.is_online,
            City.code,
            City.name,
            Branch.name,
            func.coalesce(
                func.sum(
                    DriverFinanceTransaction.debt_change_kopecks
                ),
                0,
            ).label("cash_debt_kopecks"),
        )
        .join(
            User,
            User.id == DriverProfile.user_id,
        )
        .join(
            City,
            City.id == DriverProfile.city_id,
        )
        .outerjoin(
            Branch,
            Branch.id == DriverProfile.branch_id,
        )
        .outerjoin(
            DriverFinanceTransaction,
            (
                DriverFinanceTransaction.driver_user_id
                == DriverProfile.user_id
            )
            & (
                DriverFinanceTransaction.city_id
                == DriverProfile.city_id
            ),
        )
        .where(
            DriverProfile.city_id == city.id,
            DriverProfile.is_active.is_(True),
            User.is_active.is_(True),
            City.is_active.is_(True),
        )
        .group_by(
            DriverProfile.user_id,
            User.username,
            User.phone,
            DriverProfile.rating,
            DriverProfile.is_online,
            City.code,
            City.name,
            Branch.name,
        )
    )

    if profile.role == "dispatcher":
        query = query.where(
            DriverProfile.branch_id == profile.branch_id,
        )

    rows = db.execute(
        query.order_by(
            User.username,
        )
    ).all()

    drivers = []

    for (
        driver_user_id,
        username,
        phone,
        rating,
        is_online,
        driver_city_code,
        city_name,
        branch_name,
        cash_debt_kopecks,
    ) in rows:
        drivers.append(
            {
                "driver_user_id": str(driver_user_id),
                "username": username,
                "phone": phone,
                "rating": str(rating),
                "is_online": is_online,
                "city_code": driver_city_code,
                "city_name": city_name,
                "branch_name": branch_name,
                "cash_debt_kopecks": int(cash_debt_kopecks),
                "cash_debt_rub": round(
                    int(cash_debt_kopecks) / 100,
                    2,
                ),
            }
        )

    return {
        "city_code": city.code,
        "drivers_count": len(drivers),
        "total_cash_debt_kopecks": sum(
            item["cash_debt_kopecks"]
            for item in drivers
        ),
        "drivers": drivers,
    }


@router.get("/finance/summary")
def get_dispatch_finance_summary(
    city_code: str = "obolensk",
    period_days: int = Query(default=30, ge=1, le=90),
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    """
    Финансовая сводка города или филиала диспетчера.

    Показатели поездок и погашений рассчитываются за выбранный период.
    Текущая задолженность рассчитывается за всё время.
    Денежные суммы возвращаются в копейках и рублях.
    """

    profile = get_dispatcher_profile(
        db,
        dispatcher,
    )

    if profile.role == "dispatcher":
        branch = db.get(
            Branch,
            profile.branch_id,
        )

        if branch is None or not branch.is_active:
            raise HTTPException(
                403,
                "Филиал диспетчера недоступен",
            )

        city = db.get(
            City,
            branch.city_id,
        )

        if city is None or not city.is_active:
            raise HTTPException(
                403,
                "Город филиала недоступен",
            )

        branch_id = branch.id
    else:
        city = db.scalar(
            select(City).where(
                City.code == city_code,
                City.is_active.is_(True),
            )
        )

        if city is None:
            raise HTTPException(
                404,
                "Город не найден или неактивен",
            )

        branch_id = None

    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=period_days)

    transaction_filters = [
        DriverFinanceTransaction.city_id == city.id,
    ]

    if branch_id is not None:
        transaction_filters.append(
            DriverFinanceTransaction.branch_id == branch_id,
        )

    period_filters = [
        *transaction_filters,
        DriverFinanceTransaction.created_at >= period_start,
        DriverFinanceTransaction.created_at <= period_end,
    ]

    completed_trip = (
        DriverFinanceTransaction.transaction_type
        == "completed_trip"
    )

    debt_repayment = (
        DriverFinanceTransaction.transaction_type
        == "debt_repayment"
    )

    electronic_payment = (
        DriverFinanceTransaction.payment_method.in_(
            ["card", "sbp", "driver_transfer"]
        )
    )

    totals = db.execute(
        select(
            func.count(
                DriverFinanceTransaction.id
            ).filter(
                completed_trip
            ).label("completed_trips"),

            func.coalesce(
                func.sum(
                    DriverFinanceTransaction.fare_kopecks
                ).filter(
                    completed_trip
                ),
                0,
            ).label("total_fare_kopecks"),

            func.coalesce(
                func.sum(
                    DriverFinanceTransaction.commission_kopecks
                ).filter(
                    completed_trip
                ),
                0,
            ).label("commission_accrued_kopecks"),

            func.coalesce(
                func.sum(
                    DriverFinanceTransaction.commission_kopecks
                ).filter(
                    completed_trip & electronic_payment
                ),
                0,
            ).label("electronic_commission_kopecks"),

            func.coalesce(
                func.sum(
                    DriverFinanceTransaction.fare_kopecks
                ).filter(
                    completed_trip & electronic_payment
                ),
                0,
            ).label("electronic_trip_fare_kopecks"),

            func.coalesce(
                func.sum(
                    DriverFinanceTransaction.fare_kopecks
                ).filter(
                    completed_trip
                    & (
                        DriverFinanceTransaction.payment_method
                        == "cash"
                    )
                ),
                0,
            ).label("cash_trip_fare_kopecks"),

            func.coalesce(
                func.sum(
                    -DriverFinanceTransaction.debt_change_kopecks
                ).filter(
                    debt_repayment
                ),
                0,
            ).label("debt_repaid_kopecks"),

            func.coalesce(
                func.sum(
                    -DriverFinanceTransaction.debt_change_kopecks
                ).filter(
                    debt_repayment
                    & (
                        DriverFinanceTransaction.payment_method
                        == "cash"
                    )
                ),
                0,
            ).label("cash_repaid_kopecks"),

            func.coalesce(
                func.sum(
                    -DriverFinanceTransaction.debt_change_kopecks
                ).filter(
                    debt_repayment
                    & (
                        DriverFinanceTransaction.payment_method
                        == "driver_transfer"
                    )
                ),
                0,
            ).label("transfer_repaid_kopecks"),

            func.coalesce(
                func.sum(
                    DriverFinanceTransaction.debt_change_kopecks
                ).filter(
                    completed_trip
                    & (
                        DriverFinanceTransaction.payment_method
                        == "cash"
                    )
                ),
                0,
            ).label("cash_commission_debt_kopecks"),
        )
        .where(*period_filters)
    ).one()

    current_debt_query = select(
        func.coalesce(
            func.sum(
                DriverFinanceTransaction.debt_change_kopecks
            ),
            0,
        )
    ).where(*transaction_filters)

    current_debt_kopecks = int(
        db.scalar(current_debt_query) or 0
    )

    def amount_response(value: int) -> dict:
        amount = int(value or 0)

        return {
            "kopecks": amount,
            "rub": round(amount / 100, 2),
        }

    return {
        "city": {
            "code": city.code,
            "name": city.name,
        },
        "branch_id": (
            str(branch_id)
            if branch_id is not None
            else None
        ),
        "period": {
            "days": period_days,
            "from": period_start,
            "to": period_end,
            "timezone": "UTC",
        },
        "completed_trips": int(
            totals.completed_trips or 0
        ),
        "total_trip_fare": amount_response(
            totals.total_fare_kopecks
        ),
        "commission_accrued": amount_response(
            totals.commission_accrued_kopecks
        ),
        "electronic_payments": {
            "trip_fare_turnover": amount_response(
                totals.electronic_trip_fare_kopecks
            ),
            "commission": amount_response(
                totals.electronic_commission_kopecks
            ),
        },
        "cash_payments": {
            "trip_fare_turnover": amount_response(
                totals.cash_trip_fare_kopecks
            ),
            "commission_debt_accrued": amount_response(
                totals.cash_commission_debt_kopecks
            ),
        },
        "debt_repayments": {
            "total": amount_response(
                totals.debt_repaid_kopecks
            ),
            "cash": amount_response(
                totals.cash_repaid_kopecks
            ),
            "driver_transfer": amount_response(
                totals.transfer_repaid_kopecks
            ),
        },
        "current_driver_debt": amount_response(
            current_debt_kopecks
        ),
        "accounting_note": (
            "Оборот поездок по электронным способам оплаты "
            "не является подтверждением фактического зачисления "
            "денег на расчётный счёт сервиса. Для учёта реальных "
            "поступлений потребуется интеграция с платёжным провайдером."
        ),
    }


@router.get("/drivers/{driver_user_id}/finance/transactions")
def list_dispatch_driver_finance_transactions(
    driver_user_id: UUID,
    city_code: str = "obolensk",
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    """История финансовых операций водителя для диспетчерской."""

    dispatcher_profile = get_dispatcher_profile(
        db,
        dispatcher,
    )

    if dispatcher_profile.role == "dispatcher":
        branch = db.get(
            Branch,
            dispatcher_profile.branch_id,
        )

        if branch is None or not branch.is_active:
            raise HTTPException(
                403,
                "Филиал диспетчера недоступен",
            )

        city = db.get(City, branch.city_id)

        if city is None or not city.is_active:
            raise HTTPException(
                403,
                "Город филиала недоступен",
            )
    else:
        city = db.scalar(
            select(City).where(
                City.code == city_code,
                City.is_active.is_(True),
            )
        )

        if city is None:
            raise HTTPException(
                404,
                "Город не найден или неактивен",
            )

    driver_query = (
        select(DriverProfile, User)
        .join(
            User,
            User.id == DriverProfile.user_id,
        )
        .where(
            DriverProfile.user_id == driver_user_id,
            DriverProfile.city_id == city.id,
            DriverProfile.is_active.is_(True),
            User.is_active.is_(True),
        )
    )

    if dispatcher_profile.role == "dispatcher":
        driver_query = driver_query.where(
            DriverProfile.branch_id == dispatcher_profile.branch_id,
        )

    driver_row = db.execute(driver_query).first()

    if driver_row is None:
        raise HTTPException(
            404,
            "Водитель не найден или недоступен для этого диспетчера",
        )

    driver_profile, driver_user = driver_row

    running_debt = func.sum(
        DriverFinanceTransaction.debt_change_kopecks
    ).over(
        order_by=(
            DriverFinanceTransaction.created_at,
            DriverFinanceTransaction.id,
        ),
        rows=(None, 0),
    ).label("debt_after_kopecks")

    base_filter = (
        DriverFinanceTransaction.driver_user_id == driver_user_id,
        DriverFinanceTransaction.city_id == city.id,
    )

    total_count = db.scalar(
        select(func.count(DriverFinanceTransaction.id)).where(
            *base_filter,
        )
    ) or 0

    current_debt = db.scalar(
        select(
            func.coalesce(
                func.sum(
                    DriverFinanceTransaction.debt_change_kopecks
                ),
                0,
            )
        ).where(*base_filter)
    )

    rows = db.execute(
        select(
            DriverFinanceTransaction,
            running_debt,
        )
        .where(*base_filter)
        .order_by(
            DriverFinanceTransaction.created_at.desc(),
            DriverFinanceTransaction.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()

    transactions = []

    for transaction, debt_after_kopecks in rows:
        transactions.append(
            {
                "id": str(transaction.id),
                "transaction_type": transaction.transaction_type,
                "payment_method": transaction.payment_method,
                "amount_kopecks": (
                    -transaction.debt_change_kopecks
                    if transaction.transaction_type == "debt_repayment"
                    else transaction.commission_kopecks
                ),
                "debt_change_kopecks": transaction.debt_change_kopecks,
                "debt_after_kopecks": int(
                    debt_after_kopecks or 0
                ),
                "description": transaction.description,
                "order_id": (
                    str(transaction.order_id)
                    if transaction.order_id is not None
                    else None
                ),
                "created_at": transaction.created_at,
            }
        )

    driver_branch = (
        db.get(Branch, driver_profile.branch_id)
        if driver_profile.branch_id is not None
        else None
    )

    return {
        "driver": {
            "user_id": str(driver_user.id),
            "username": driver_user.username,
            "phone": driver_user.phone,
            "city_code": city.code,
            "city_name": city.name,
            "branch_name": (
                driver_branch.name
                if driver_branch is not None
                else None
            ),
        },
        "current_debt_kopecks": int(current_debt or 0),
        "total_transactions": int(total_count),
        "limit": limit,
        "offset": offset,
        "transactions": transactions,
    }
