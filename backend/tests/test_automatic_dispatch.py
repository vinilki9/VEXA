"""In-memory DB integration for the dispatcher-free order assignment loop.

SQLite does not exercise PostgreSQL SKIP LOCKED, so concurrent-worker behavior
must also be checked in PostgreSQL before a production rollout.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.dispatch_engine import dispatch_tick, process_automatic_dispatch
from app.driver_api import (accept_driver_order_offer, reject_driver_order_offer,
                            update_driver_order_status, DriverOrderStatusRequest)
from app.driver_order_offer_models import DriverOrderOffer
from app.models import (City, Branch, DriverProfile, DriverLocation, Order,
                        OrderStatusHistory, User, Vehicle, DriverFinanceTransaction, DriverWalletTransaction)


@pytest.fixture
def state():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        city = City(code="vexa-autodisp", name="Тест")
        db.add(city)
        db.flush()
        branch = Branch(city_id=city.id, name="Главный")
        customer = User(username="customer-auto")
        db.add_all([branch, customer])
        db.commit()
        yield db, city, branch, customer
    Base.metadata.drop_all(engine)
    engine.dispose()


def make_order(db, city, branch, passenger, *, status="new", age_seconds=0):
    order = Order(
        city_id=city.id, branch_id=branch.id, passenger_user_id=passenger.id,
        public_number=f"VEXA-TEST-{uuid4()}", idempotency_key=str(uuid4()),
        customer_name="Пассажир", customer_phone="+79999990000",
        pickup_address="A", destination_address="B", pickup_latitude=55.75,
        pickup_longitude=37.61, destination_latitude=55.76,
        destination_longitude=37.62, payment_method="cash", status=status,
        created_at=datetime.now(timezone.utc) - timedelta(seconds=age_seconds),
    )
    db.add(order)
    db.commit()
    return order


def make_driver(db, city, branch, *, lat=55.75, lon=37.61, online=True):
    driver = User(username=f"vexa-driver-{uuid4()}")
    db.add(driver)
    db.flush()
    profile = DriverProfile(user_id=driver.id, city_id=city.id, branch_id=branch.id,
                            is_active=True, is_online=online)
    db.add(profile)
    db.flush()
    car = Vehicle(driver_user_id=driver.id, city_id=city.id, make="Lada",
                  model="Vesta", color="Белый", license_plate=f"A{str(uuid4())[:8]}")
    position = DriverLocation(driver_user_id=driver.id, latitude=lat, longitude=lon,
                              recorded_at=datetime.now(timezone.utc),
                              updated_at=datetime.now(timezone.utc))
    db.add_all([car, position])
    db.commit()
    return driver, profile, car


def offers(db, order):
    return db.scalars(select(DriverOrderOffer).where(DriverOrderOffer.order_id == order.id)
                      .order_by(DriverOrderOffer.attempt_number)).all()


def test_order_automatically_offered_and_driver_accepts_without_dispatcher(state):
    db, city, branch, passenger = state
    driver, _, car = make_driver(db, city, branch)
    order = make_order(db, city, branch, passenger)
    count = process_automatic_dispatch(db)
    db.refresh(order)
    assert count["started"] == 1
    assert count["offered"] == 1
    assert order.status == "accepted"
    assert len(offers(db, order)) == 1
    result = accept_driver_order_offer(offers(db, order)[0].id, driver=driver, db=db)
    assert result["success"] is True
    db.refresh(order)
    assert order.status == "assigned"
    assert order.driver_user_id == driver.id
    assert order.vehicle_id == car.id
    assert process_automatic_dispatch(db)["offered"] == 0
    assert len(offers(db, order)) == 1
    transitions = db.scalars(select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id)
                             .order_by(OrderStatusHistory.created_at)).all()
    assert {(e.old_status, e.new_status) for e in transitions} == {
        ("new", "accepted"), ("accepted", "assigned")}


def test_repoll_does_not_duplicate_pending_offer(state):
    db, city, branch, passenger = state
    make_driver(db, city, branch)
    order = make_order(db, city, branch, passenger)
    process_automatic_dispatch(db)
    assert process_automatic_dispatch(db)["offered"] == 0
    assert len(offers(db, order)) == 1


def test_driver_rejects_and_next_driver_gets_offer_automatically(state):
    db, city, branch, passenger = state
    nearest, _, _ = make_driver(db, city, branch, lat=55.7501)
    other, _, _ = make_driver(db, city, branch, lat=55.76)
    order = make_order(db, city, branch, passenger)
    process_automatic_dispatch(db)
    first = offers(db, order)[0]
    assert first.driver_user_id == nearest.id
    result = reject_driver_order_offer(first.id, driver=nearest, db=db)
    assert result["success"] is True
    assert result["next_offer"]["offered"] is True
    assert [x.status for x in offers(db, order)] == ["rejected", "pending"]
    assert offers(db, order)[1].driver_user_id == other.id


def test_expired_offer_moves_to_next_driver_without_dispatcher(state):
    db, city, branch, passenger = state
    first, _, _ = make_driver(db, city, branch, lat=55.7501)
    second, _, _ = make_driver(db, city, branch, lat=55.76)
    order = make_order(db, city, branch, passenger)
    process_automatic_dispatch(db)
    old_offer = offers(db, order)[0]
    assert old_offer.driver_user_id == first.id
    old_offer.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    stats = dispatch_tick(db)
    assert stats["expired_handled"] == 1
    assert stats["offered"] == 1
    assert [(x.driver_user_id, x.status) for x in offers(db, order)] == [
        (first.id, "expired"), (second.id, "pending")]


def test_no_driver_found_after_timeout_is_terminal_not_billable(state):
    db, city, branch, passenger = state
    order = make_order(db, city, branch, passenger, age_seconds=500)
    stats = process_automatic_dispatch(db)
    db.refresh(order)
    assert stats["no_driver_found"] == 1
    assert order.status == "no_driver_found"
    assert order.driver_user_id is None
    assert order.vehicle_id is None
    assert offers(db, order) == []
    assert process_automatic_dispatch(db)["scanned"] == 0
    assert db.scalar(select(func.count()).select_from(OrderStatusHistory).where(
        OrderStatusHistory.order_id == order.id,
        OrderStatusHistory.new_status == "no_driver_found")) == 1


def test_wait_for_driver_then_offer_when_one_comes_online(state):
    db, city, branch, passenger = state
    order = make_order(db, city, branch, passenger)
    first = process_automatic_dispatch(db)
    assert first["started"] == 1 and first["waiting"] == 1
    make_driver(db, city, branch)
    second = process_automatic_dispatch(db)
    assert second["offered"] == 1
    assert len(offers(db, order)) == 1


def test_cancelled_order_never_gets_new_offer(state):
    db, city, branch, passenger = state
    make_driver(db, city, branch)
    order = make_order(db, city, branch, passenger, status="cancelled")
    assert process_automatic_dispatch(db)["scanned"] == 0
    assert offers(db, order) == []


def test_full_cash_trip_lifecycle_and_exactly_once_finance(state):
    db, city, branch, passenger = state
    driver, _, _ = make_driver(db, city, branch)
    order = make_order(db, city, branch, passenger)
    order.price_kopecks = 30000
    db.commit()
    process_automatic_dispatch(db)
    offer = offers(db, order)[0]
    accept_driver_order_offer(offer.id, driver=driver, db=db)
    for step in ("arrived", "in_progress", "completed"):
        answer = update_driver_order_status(order.id, DriverOrderStatusRequest(status=step),
                                            driver=driver, db=db)
        assert answer["success"] is True
        db.refresh(order)
        assert order.status == step
    # Client retry after a lost HTTP response must not duplicate payouts.
    assert update_driver_order_status(order.id, DriverOrderStatusRequest(status="completed"),
                                      driver=driver, db=db)["success"] is True
    assert db.scalar(select(func.count()).select_from(DriverFinanceTransaction).where(
        DriverFinanceTransaction.order_id == order.id)) == 1
    assert db.scalar(select(func.count()).select_from(DriverWalletTransaction).where(
        DriverWalletTransaction.order_id == order.id)) == 1


def test_pending_offer_not_duplicated_across_different_orders(state):
    db, city, branch, passenger = state
    driver, _, _ = make_driver(db, city, branch)
    order_a = make_order(db, city, branch, passenger)
    order_b = make_order(db, city, branch, passenger)
    counts = process_automatic_dispatch(db)
    assert counts["offered"] == 1
    assert len(offers(db, order_a)) + len(offers(db, order_b)) == 1
    assert process_automatic_dispatch(db)["offered"] == 0


def test_stale_gps_driver_excluded_until_location_refresh(state):
    db, city, branch, passenger = state
    driver, _, _ = make_driver(db, city, branch)
    location = db.get(DriverLocation, driver.id)
    location.recorded_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    order = make_order(db, city, branch, passenger)
    assert process_automatic_dispatch(db)["waiting"] == 1
    assert offers(db, order) == []
    location.recorded_at = datetime.now(timezone.utc)
    db.commit()
    assert process_automatic_dispatch(db)["offered"] == 1


def test_timeout_after_expired_offer_never_creates_late_offer(state):
    db, city, branch, passenger = state
    first, _, _ = make_driver(db, city, branch, lat=55.7501)
    second, _, _ = make_driver(db, city, branch, lat=55.76)
    order = make_order(db, city, branch, passenger)
    process_automatic_dispatch(db)
    old_offer = offers(db, order)[0]
    old_offer.expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    order.created_at = datetime.now(timezone.utc) - timedelta(seconds=500)
    db.commit()
    stats = dispatch_tick(db)
    db.refresh(order)
    assert stats["expired_handled"] == 1
    assert stats["no_driver_found"] == 1
    assert order.status == "no_driver_found"
    assert len(offers(db, order)) == 1
    assert offers(db, order)[0].status == "expired"
