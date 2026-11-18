
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
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
    DriverWallet,
    DriverWalletTransaction,
    Order,
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
    """Текущий баланс кошелька водителей города или филиала."""

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
                DriverWallet.balance_kopecks,
                0,
            ).label("balance_kopecks"),
            func.coalesce(
                DriverWallet.reserved_kopecks,
                0,
            ).label("reserved_kopecks"),
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
            DriverWallet,
            DriverWallet.driver_user_id == DriverProfile.user_id,
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
        balance_kopecks,
        reserved_kopecks,
    ) in rows:
        balance = int(balance_kopecks or 0)
        reserved = int(reserved_kopecks or 0)
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
                "balance_kopecks": balance,
                "balance_rub": round(balance / 100, 2),
                "reserved_kopecks": reserved,
                "available_kopecks": max(balance - reserved, 0),
            }
        )

    return {
        "city_code": city.code,
        "drivers_count": len(drivers),
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
    """История операций кошелька водителя для диспетчерской."""

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

    wallet = db.scalar(
        select(DriverWallet).where(
            DriverWallet.driver_user_id == driver_user_id,
            DriverWallet.city_id == city.id,
        )
    )

    base_filter = (
        DriverWalletTransaction.driver_user_id == driver_user_id,
    )

    total_count = db.scalar(
        select(func.count(DriverWalletTransaction.id)).where(
            *base_filter,
        )
    ) or 0

    rows = db.execute(
        select(
            DriverWalletTransaction,
            Order.public_number,
        )
        .outerjoin(
            Order,
            Order.id == DriverWalletTransaction.order_id,
        )
        .where(*base_filter)
        .order_by(
            DriverWalletTransaction.created_at.desc(),
            DriverWalletTransaction.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()

    transactions = []

    for transaction, order_public_number in rows:
        transactions.append(
            {
                "id": str(transaction.id),
                "transaction_type": transaction.transaction_type,
                "payment_method": transaction.payment_method,
                "amount_kopecks": transaction.balance_change_kopecks,
                "balance_change_kopecks": transaction.balance_change_kopecks,
                "balance_after_kopecks": transaction.balance_after_kopecks,
                "reserved_after_kopecks": transaction.reserved_after_kopecks,
                "description": transaction.description,
                "order_id": (
                    str(transaction.order_id)
                    if transaction.order_id is not None
                    else None
                ),
                "order_public_number": order_public_number,
                "created_at": transaction.created_at,
            }
        )

    driver_branch = (
        db.get(Branch, driver_profile.branch_id)
        if driver_profile.branch_id is not None
        else None
    )

    current_balance = (
        int(wallet.balance_kopecks)
        if wallet is not None
        else 0
    )
    reserved_balance = (
        int(wallet.reserved_kopecks)
        if wallet is not None
        else 0
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
        "current_balance_kopecks": current_balance,
        "reserved_kopecks": reserved_balance,
        "available_kopecks": max(
            current_balance - reserved_balance,
            0,
        ),
        "total_transactions": int(total_count),
        "limit": limit,
        "offset": offset,
        "transactions": transactions,
    }


@router.get("/finance/export.xlsx")
def export_dispatch_finance_excel(
    date_from: date = Query(...),
    date_to: date = Query(...),
    city_code: str = Query(default="obolensk", min_length=1, max_length=80),
    branch_id: UUID | None = Query(default=None),
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    """Экспорт финансового отчёта города или филиала в Excel."""

    if date_to < date_from:
        raise HTTPException(
            422,
            "Дата окончания не может быть раньше даты начала",
        )

    if (date_to - date_from).days > 366:
        raise HTTPException(
            422,
            "Период экспорта не может превышать 367 календарных дней",
        )

    profile = get_dispatcher_profile(db, dispatcher)

    if profile.role == "dispatcher":
        selected_branch = db.get(Branch, profile.branch_id)
        if selected_branch is None or not selected_branch.is_active:
            raise HTTPException(403, "Филиал диспетчера недоступен")
        if branch_id is not None and branch_id != selected_branch.id:
            raise HTTPException(403, "Нет доступа к выбранному филиалу")
        selected_branch_id = selected_branch.id
        city = db.get(City, selected_branch.city_id)
    else:
        city = db.scalar(
            select(City).where(
                City.code == city_code,
                City.is_active.is_(True),
            )
        )
        selected_branch_id = branch_id

        if selected_branch_id is not None:
            selected_branch = db.get(Branch, selected_branch_id)
            if (
                selected_branch is None
                or not selected_branch.is_active
                or selected_branch.city_id != city.id
            ):
                raise HTTPException(404, "Филиал не найден в выбранном городе")

    if city is None or not city.is_active:
        raise HTTPException(404, "Город не найден или неактивен")

    period_start = datetime.combine(
        date_from, time.min, tzinfo=timezone.utc
    )
    period_end_exclusive = datetime.combine(
        date_to + timedelta(days=1), time.min, tzinfo=timezone.utc
    )

    scope_filters = [
        DriverFinanceTransaction.city_id == city.id,
    ]
    if selected_branch_id is not None:
        scope_filters.append(
            DriverFinanceTransaction.branch_id == selected_branch_id
        )

    period_filters = [
        *scope_filters,
        DriverFinanceTransaction.created_at >= period_start,
        DriverFinanceTransaction.created_at < period_end_exclusive,
    ]

    transaction_rows = db.execute(
        select(
            DriverFinanceTransaction,
            User.username,
            User.phone,
            Branch.name,
        )
        .join(
            User,
            User.id == DriverFinanceTransaction.driver_user_id,
        )
        .outerjoin(
            Branch,
            Branch.id == DriverFinanceTransaction.branch_id,
        )
        .where(*period_filters)
        .order_by(
            User.username,
            DriverFinanceTransaction.created_at,
            DriverFinanceTransaction.id,
        )
    ).all()

    debt_rows = db.execute(
        select(
            DriverFinanceTransaction.driver_user_id,
            func.coalesce(
                func.sum(DriverFinanceTransaction.debt_change_kopecks),
                0,
            ),
        )
        .where(*scope_filters)
        .group_by(DriverFinanceTransaction.driver_user_id)
    ).all()
    current_debts = {
        driver_id: int(debt or 0)
        for driver_id, debt in debt_rows
    }

    driver_summary = {}
    for transaction, username, phone, branch_name in transaction_rows:
        driver_id = transaction.driver_user_id
        if driver_id not in driver_summary:
            driver_summary[driver_id] = {
                "username": username or "",
                "phone": phone or "",
                "branch": branch_name or "",
                "trips": 0,
                "fare": 0,
                "commission": 0,
                "repayments": 0,
                "debt_change": 0,
            }

        item = driver_summary[driver_id]
        if transaction.transaction_type == "completed_trip":
            item["trips"] += 1
            item["fare"] += int(transaction.fare_kopecks or 0)
            item["commission"] += int(transaction.commission_kopecks or 0)
        elif transaction.transaction_type == "debt_repayment":
            item["repayments"] += max(
                0, -int(transaction.debt_change_kopecks or 0)
            )
        item["debt_change"] += int(
            transaction.debt_change_kopecks or 0
        )

    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "Сводка"
    summary_sheet.append(["Финансовый отчёт VEXA"])
    summary_sheet.append(["Город", city.name])
    summary_sheet.append(["Филиал", "Все филиалы" if selected_branch_id is None else db.get(Branch, selected_branch_id).name])
    summary_sheet.append(["Период с", date_from.isoformat()])
    summary_sheet.append(["Период по", date_to.isoformat()])
    summary_sheet.append([])
    summary_sheet.append([
        "Водитель", "Телефон", "Филиал", "Поездок",
        "Оборот, ₽", "Комиссия, ₽", "Погашения, ₽",
        "Изменение долга за период, ₽", "Текущий долг, ₽",
    ])

    for driver_id, item in sorted(
        driver_summary.items(),
        key=lambda pair: pair[1]["username"].casefold(),
    ):
        summary_sheet.append([
            item["username"],
            item["phone"],
            item["branch"],
            item["trips"],
            item["fare"] / 100,
            item["commission"] / 100,
            item["repayments"] / 100,
            item["debt_change"] / 100,
            current_debts.get(driver_id, 0) / 100,
        ])

    details_sheet = workbook.create_sheet("Операции")
    details_sheet.append([
        "Дата и время UTC", "Город", "Филиал", "Водитель",
        "Тип операции", "Способ оплаты", "Стоимость поездки, ₽",
        "Ставка комиссии, %", "Комиссия, ₽", "Заработок водителя, ₽",
        "Изменение долга, ₽", "Описание", "ID заказа",
    ])

    for transaction, username, phone, branch_name in transaction_rows:
        created_at = transaction.created_at
        if created_at is not None and created_at.tzinfo is not None:
            created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
        details_sheet.append([
            created_at,
            city.name,
            branch_name or "",
            username or "",
            transaction.transaction_type,
            transaction.payment_method,
            int(transaction.fare_kopecks or 0) / 100,
            float(transaction.commission_rate_percent or 0),
            int(transaction.commission_kopecks or 0) / 100,
            int(transaction.driver_earning_kopecks or 0) / 100,
            int(transaction.debt_change_kopecks or 0) / 100,
            transaction.description or "",
            str(transaction.order_id) if transaction.order_id else "",
        ])

    branches_sheet = workbook.create_sheet("Филиалы")
    branches_sheet.append([
        "Город", "Филиал", "Водителей с операциями", "Поездок",
        "Оборот, ₽", "Комиссия, ₽", "Погашения, ₽",
        "Текущий долг, ₽",
    ])
    branches_summary = {}
    for driver_id, item in driver_summary.items():
        key = item["branch"] or "Без филиала"
        branch_item = branches_summary.setdefault(key, {
            "drivers": 0, "trips": 0, "fare": 0,
            "commission": 0, "repayments": 0,
        })
        branch_item["drivers"] += 1
        branch_item["trips"] += item["trips"]
        branch_item["fare"] += item["fare"]
        branch_item["commission"] += item["commission"]
        branch_item["repayments"] += item["repayments"]

    branch_debts = {}
    debt_by_branch_rows = db.execute(
        select(
            Branch.name,
            func.coalesce(
                func.sum(DriverFinanceTransaction.debt_change_kopecks),
                0,
            ),
        )
        .outerjoin(
            DriverFinanceTransaction,
            DriverFinanceTransaction.branch_id == Branch.id,
        )
        .where(Branch.city_id == city.id)
        .group_by(Branch.name)
    ).all()
    branch_debts = {name: int(debt or 0) for name, debt in debt_by_branch_rows}

    for branch_name, item in sorted(branches_summary.items()):
        branches_sheet.append([
            city.name,
            branch_name,
            item["drivers"],
            item["trips"],
            item["fare"] / 100,
            item["commission"] / 100,
            item["repayments"] / 100,
            branch_debts.get(branch_name, 0) / 100,
        ])

    header_fill = PatternFill("solid", fgColor="17365D")
    header_font = Font(color="FFFFFF", bold=True)
    for sheet in workbook.worksheets:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(vertical="center")
        for column_cells in sheet.columns:
            max_length = max(
                (len(str(cell.value)) if cell.value is not None else 0)
                for cell in column_cells
            )
            sheet.column_dimensions[column_cells[0].column_letter].width = min(
                max(max_length + 2, 12), 42
            )

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    filename = (
        f"vexa_finance_{city.code}_{date_from.isoformat()}_"
        f"{date_to.isoformat()}.xlsx"
    )

    return StreamingResponse(
        output,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
