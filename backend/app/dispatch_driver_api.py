
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
    """Сводка поездок за период и текущих балансов кошельков."""
    profile = get_dispatcher_profile(db, dispatcher)
    if profile.role == "dispatcher":
        branch = db.get(Branch, profile.branch_id)
        if branch is None or not branch.is_active:
            raise HTTPException(403, "Филиал диспетчера недоступен")
        city = db.get(City, branch.city_id)
        if city is None or not city.is_active:
            raise HTTPException(403, "Город филиала недоступен")
        branch_id = branch.id
    else:
        city = db.scalar(select(City).where(
            City.code == city_code,
            City.is_active.is_(True),
        ))
        if city is None:
            raise HTTPException(404, "Город не найден или неактивен")
        branch_id = None

    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=period_days)
    trip_filters = [DriverFinanceTransaction.city_id == city.id]
    if branch_id is not None:
        trip_filters.append(DriverFinanceTransaction.branch_id == branch_id)
    period_filters = [
        *trip_filters,
        DriverFinanceTransaction.created_at >= period_start,
        DriverFinanceTransaction.created_at <= period_end,
    ]

    completed_trip = DriverFinanceTransaction.transaction_type == "completed_trip"
    electronic_method = DriverFinanceTransaction.payment_method.in_(["card", "sbp"])
    pay_driver_method = DriverFinanceTransaction.payment_method.in_(["cash", "driver_transfer"])
    totals = db.execute(select(
        func.count(DriverFinanceTransaction.id).filter(completed_trip).label("completed_trips"),
        func.coalesce(func.sum(DriverFinanceTransaction.fare_kopecks).filter(completed_trip), 0).label("total_fare_kopecks"),
        func.coalesce(func.sum(DriverFinanceTransaction.commission_kopecks).filter(completed_trip), 0).label("commission_accrued_kopecks"),
        func.coalesce(func.sum(DriverFinanceTransaction.commission_kopecks).filter(completed_trip & electronic_method), 0).label("electronic_commission_kopecks"),
        func.coalesce(func.sum(DriverFinanceTransaction.fare_kopecks).filter(completed_trip & electronic_method), 0).label("electronic_trip_fare_kopecks"),
        func.coalesce(func.sum(DriverFinanceTransaction.fare_kopecks).filter(completed_trip & pay_driver_method), 0).label("pay_driver_trip_fare_kopecks"),
        func.coalesce(func.sum(DriverFinanceTransaction.fare_kopecks).filter(completed_trip & (DriverFinanceTransaction.payment_method == "cash")), 0).label("cash_trip_fare_kopecks"),
        func.coalesce(func.sum(DriverFinanceTransaction.fare_kopecks).filter(completed_trip & (DriverFinanceTransaction.payment_method == "driver_transfer")), 0).label("transfer_trip_fare_kopecks"),
    ).where(*period_filters)).one()

    wallet_query = (
        select(DriverWallet)
        .join(DriverProfile, DriverProfile.user_id == DriverWallet.driver_user_id)
        .where(DriverProfile.city_id == city.id)
    )
    if branch_id is not None:
        wallet_query = wallet_query.where(DriverProfile.branch_id == branch_id)
    wallets = db.scalars(wallet_query).all()

    total_balance = sum(int(wallet.balance_kopecks or 0) for wallet in wallets)
    total_reserved = sum(int(wallet.reserved_kopecks or 0) for wallet in wallets)
    positive_balance = sum(max(int(wallet.balance_kopecks or 0), 0) for wallet in wallets)
    available_balance = sum(
        max(int(wallet.balance_kopecks or 0) - int(wallet.reserved_kopecks or 0), 0)
        for wallet in wallets
    )
    current_debt = sum(max(-int(wallet.balance_kopecks or 0), 0) for wallet in wallets)
    negative_wallet_count = sum(1 for wallet in wallets if int(wallet.balance_kopecks or 0) < 0)

    wallet_tx_filters = [
        DriverWalletTransaction.created_at >= period_start,
        DriverWalletTransaction.created_at <= period_end,
        DriverWalletTransaction.transaction_type.in_(["commission_debit", "electronic_earning_credit"]),
        Order.city_id == city.id,
    ]
    if branch_id is not None:
        wallet_tx_filters.append(Order.branch_id == branch_id)
    wallet_transactions = db.scalars(
        select(DriverWalletTransaction)
        .join(Order, Order.id == DriverWalletTransaction.order_id)
        .where(*wallet_tx_filters)
        .order_by(DriverWalletTransaction.created_at, DriverWalletTransaction.id)
    ).all()

    commission_debt_accrued = 0
    automatic_electronic_repayment = 0
    for tx in wallet_transactions:
        change = int(tx.balance_change_kopecks or 0)
        after_balance = int(tx.balance_after_kopecks or 0)
        before_balance = after_balance - change
        if tx.transaction_type == "commission_debit" and tx.payment_method in ("cash", "driver_transfer"):
            commission_debt_accrued += max(
                max(-after_balance, 0) - max(-before_balance, 0),
                0,
            )
        elif tx.transaction_type == "electronic_earning_credit" and tx.payment_method in ("card", "sbp"):
            automatic_electronic_repayment += min(max(change, 0), max(-before_balance, 0))

    def amount_response(value: int) -> dict:
        amount = int(value or 0)
        return {"kopecks": amount, "rub": round(amount / 100, 2)}

    return {
        "city": {"code": city.code, "name": city.name},
        "branch_id": str(branch_id) if branch_id is not None else None,
        "period": {
            "days": period_days,
            "from": period_start,
            "to": period_end,
            "timezone": "UTC",
        },
        "completed_trips": int(totals.completed_trips or 0),
        "total_trip_fare": amount_response(totals.total_fare_kopecks),
        "commission_accrued": amount_response(totals.commission_accrued_kopecks),
        "electronic_payments": {
            "trip_fare_turnover": amount_response(totals.electronic_trip_fare_kopecks),
            "commission": amount_response(totals.electronic_commission_kopecks),
        },
        "cash_payments": {
            "trip_fare_turnover": amount_response(totals.pay_driver_trip_fare_kopecks),
            "cash_trip_fare_turnover": amount_response(totals.cash_trip_fare_kopecks),
            "commission_debt_accrued": amount_response(commission_debt_accrued),
        },
        "driver_transfer_payments": {
            "trip_fare_turnover": amount_response(totals.transfer_trip_fare_kopecks),
        },
        "debt_repayments": {
            "total": amount_response(automatic_electronic_repayment),
            "automatic_electronic_credit": amount_response(automatic_electronic_repayment),
            "cash": amount_response(0),
            "driver_transfer": amount_response(0),
        },
        "current_driver_debt": amount_response(current_debt),
        "wallet_summary": {
            "balance": amount_response(total_balance),
            "positive_balance": amount_response(positive_balance),
            "reserved": amount_response(total_reserved),
            "available": amount_response(available_balance),
            "negative_balance_debt": amount_response(current_debt),
            "drivers_with_negative_balance": negative_wallet_count,
            "drivers_count": len(wallets),
        },
        "accounting_note": (
            "Отрицательный баланс каждого водителя отдельно отражает его долг VEXA. "
            "Комиссия за наличные и перевод водителю списывается с кошелька; "
            "при недостатке средств баланс становится отрицательным. "
            "Электронные начисления сначала покрывают отрицательный баланс. "
            "Наличные и перевод водителю не являются электронными поступлениями. "
            "Фактические расчёты по картам и СБП требуют интеграции платёжного провайдера."
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
        raise HTTPException(422, "Дата окончания не может быть раньше даты начала")
    if (date_to - date_from).days > 366:
        raise HTTPException(422, "Период экспорта не может превышать 367 календарных дней")

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
        city = db.scalar(select(City).where(
            City.code == city_code,
            City.is_active.is_(True),
        ))
        selected_branch_id = branch_id
        if selected_branch_id is not None:
            selected_branch = db.get(Branch, selected_branch_id)
            if (
                city is None
                or selected_branch is None
                or not selected_branch.is_active
                or selected_branch.city_id != city.id
            ):
                raise HTTPException(404, "Филиал не найден в выбранном городе")

    if city is None or not city.is_active:
        raise HTTPException(404, "Город не найден или неактивен")

    period_start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    period_end_exclusive = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)

    trip_scope_filters = [DriverFinanceTransaction.city_id == city.id]
    if selected_branch_id is not None:
        trip_scope_filters.append(DriverFinanceTransaction.branch_id == selected_branch_id)
    trip_period_filters = [
        *trip_scope_filters,
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
        .join(User, User.id == DriverFinanceTransaction.driver_user_id)
        .outerjoin(Branch, Branch.id == DriverFinanceTransaction.branch_id)
        .where(*trip_period_filters)
        .order_by(User.username, DriverFinanceTransaction.created_at, DriverFinanceTransaction.id)
    ).all()

    wallet_query = (
        select(DriverWallet, User.username, User.phone, Branch.name)
        .join(DriverProfile, DriverProfile.user_id == DriverWallet.driver_user_id)
        .join(User, User.id == DriverWallet.driver_user_id)
        .outerjoin(Branch, Branch.id == DriverProfile.branch_id)
        .where(DriverProfile.city_id == city.id)
    )
    if selected_branch_id is not None:
        wallet_query = wallet_query.where(DriverProfile.branch_id == selected_branch_id)
    wallet_rows = db.execute(wallet_query.order_by(User.username)).all()

    current_debts = {
        wallet.driver_user_id: max(-int(wallet.balance_kopecks or 0), 0)
        for wallet, username, phone, branch_name in wallet_rows
    }
    wallet_by_driver = {
        wallet.driver_user_id: wallet
        for wallet, username, phone, branch_name in wallet_rows
    }
    driver_meta = {
        wallet.driver_user_id: {
            "username": username or "",
            "phone": phone or "",
            "branch": branch_name or "",
        }
        for wallet, username, phone, branch_name in wallet_rows
    }

    wallet_tx_query = (
        select(
            DriverWalletTransaction,
            User.username,
            User.phone,
            Order.public_number,
        )
        .join(User, User.id == DriverWalletTransaction.driver_user_id)
        .outerjoin(Order, Order.id == DriverWalletTransaction.order_id)
        .outerjoin(DriverProfile, DriverProfile.user_id == DriverWalletTransaction.driver_user_id)
        .where(
            DriverWalletTransaction.created_at >= period_start,
            DriverWalletTransaction.created_at < period_end_exclusive,
            func.coalesce(Order.city_id, DriverProfile.city_id) == city.id,
        )
    )
    if selected_branch_id is not None:
        wallet_tx_query = wallet_tx_query.where(
            func.coalesce(Order.branch_id, DriverProfile.branch_id) == selected_branch_id
        )
    wallet_tx_rows = db.execute(wallet_tx_query.order_by(
        DriverWalletTransaction.created_at,
        DriverWalletTransaction.id,
    )).all()

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
            }
        item = driver_summary[driver_id]
        if transaction.transaction_type == "completed_trip":
            item["trips"] += 1
            item["fare"] += int(transaction.fare_kopecks or 0)
            item["commission"] += int(transaction.commission_kopecks or 0)
        driver_meta.setdefault(driver_id, {
            "username": username or "",
            "phone": phone or "",
            "branch": branch_name or "",
        })

    driver_wallet_ops = {}
    for tx, username, phone, order_number in wallet_tx_rows:
        driver_id = tx.driver_user_id
        if driver_id not in driver_wallet_ops:
            driver_wallet_ops[driver_id] = {
                "commission_debt_accrued": 0,
                "automatic_repayment": 0,
            }
        change = int(tx.balance_change_kopecks or 0)
        after_balance = int(tx.balance_after_kopecks or 0)
        before_balance = after_balance - change
        if tx.transaction_type == "commission_debit" and tx.payment_method in ("cash", "driver_transfer"):
            driver_wallet_ops[driver_id]["commission_debt_accrued"] += max(
                max(-after_balance, 0) - max(-before_balance, 0), 0
            )
        elif tx.transaction_type == "electronic_earning_credit" and tx.payment_method in ("card", "sbp"):
            driver_wallet_ops[driver_id]["automatic_repayment"] += min(
                max(change, 0), max(-before_balance, 0)
            )

    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "Сводка"
    summary_sheet.append(["Финансовый отчёт VEXA"])
    summary_sheet.append(["Город", city.name])
    selected_branch_name = "Все филиалы"
    if selected_branch_id is not None:
        selected_branch_name = db.get(Branch, selected_branch_id).name
    summary_sheet.append(["Филиал", selected_branch_name])
    summary_sheet.append(["Период с", date_from.isoformat()])
    summary_sheet.append(["Период по", date_to.isoformat()])
    summary_sheet.append([])
    summary_sheet.append([
        "Водитель", "Телефон", "Филиал", "Поездок",
        "Оборот поездок, ₽", "Комиссия начислена, ₽",
        "Прирост долга по комиссии, ₽", "Автопогашение электронными начислениями, ₽",
        "Текущий долг, ₽", "Текущий баланс, ₽", "Резерв, ₽", "Доступно, ₽",
    ])

    all_driver_ids = set(driver_summary) | set(driver_wallet_ops) | set(current_debts)
    for driver_id in sorted(
        all_driver_ids,
        key=lambda value: driver_meta.get(value, {}).get("username", "").casefold(),
    ):
        meta = driver_meta.get(driver_id, {})
        trip = driver_summary.get(driver_id, {})
        ops = driver_wallet_ops.get(driver_id, {})
        wallet = wallet_by_driver.get(driver_id)
        balance = int(wallet.balance_kopecks or 0) if wallet else 0
        reserved = int(wallet.reserved_kopecks or 0) if wallet else 0
        summary_sheet.append([
            meta.get("username", ""),
            meta.get("phone", ""),
            meta.get("branch", ""),
            trip.get("trips", 0),
            trip.get("fare", 0) / 100,
            trip.get("commission", 0) / 100,
            ops.get("commission_debt_accrued", 0) / 100,
            ops.get("automatic_repayment", 0) / 100,
            current_debts.get(driver_id, 0) / 100,
            balance / 100,
            reserved / 100,
            max(balance - reserved, 0) / 100,
        ])

    details_sheet = workbook.create_sheet("Поездки")
    details_sheet.append([
        "Дата и время UTC", "Город", "Филиал", "Водитель",
        "Тип операции", "Способ оплаты", "Стоимость поездки, ₽",
        "Ставка комиссии, %", "Комиссия, ₽", "Заработок водителя, ₽",
        "Изменение баланса, ₽", "Описание", "ID заказа",
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
            int(transaction.balance_change_kopecks or 0) / 100,
            transaction.description or "",
            str(transaction.order_id) if transaction.order_id else "",
        ])

    wallet_sheet = workbook.create_sheet("Операции кошелька")
    wallet_sheet.append([
        "Дата и время UTC", "Водитель", "Телефон", "Тип операции",
        "Способ оплаты", "Изменение баланса, ₽", "Баланс после, ₽",
        "Резерв после, ₽", "ID заказа", "Номер заказа", "Описание",
    ])
    for tx, username, phone, order_number in wallet_tx_rows:
        created_at = tx.created_at
        if created_at is not None and created_at.tzinfo is not None:
            created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
        wallet_sheet.append([
            created_at,
            username or "",
            phone or "",
            tx.transaction_type,
            tx.payment_method or "",
            int(tx.balance_change_kopecks or 0) / 100,
            int(tx.balance_after_kopecks or 0) / 100,
            int(tx.reserved_after_kopecks or 0) / 100,
            str(tx.order_id) if tx.order_id else "",
            order_number or "",
            tx.description or "",
        ])

    branches_sheet = workbook.create_sheet("Филиалы")
    branches_sheet.append([
        "Город", "Филиал", "Водителей с операциями", "Поездок",
        "Оборот, ₽", "Комиссия, ₽", "Текущий долг, ₽",
    ])
    branches_summary = {}
    for driver_id, item in driver_summary.items():
        key = item["branch"] or "Без филиала"
        branch_item = branches_summary.setdefault(key, {
            "drivers": set(), "trips": 0, "fare": 0, "commission": 0,
        })
        branch_item["drivers"].add(driver_id)
        branch_item["trips"] += item["trips"]
        branch_item["fare"] += item["fare"]
        branch_item["commission"] += item["commission"]

    current_branch_debts = {}
    for wallet, username, phone, branch_name in wallet_rows:
        key = branch_name or "Без филиала"
        current_branch_debts[key] = current_branch_debts.get(key, 0) + max(
            -int(wallet.balance_kopecks or 0), 0
        )
    for branch_name, item in sorted(branches_summary.items()):
        branches_sheet.append([
            city.name,
            branch_name,
            len(item["drivers"]),
            item["trips"],
            item["fare"] / 100,
            item["commission"] / 100,
            current_branch_debts.get(branch_name, 0) / 100,
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
    filename = f"vexa_finance_{city.code}_{date_from.isoformat()}_{date_to.isoformat()}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
