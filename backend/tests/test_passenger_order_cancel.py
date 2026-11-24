"""SQLite tests for passenger cancellation without optional JWT dependencies.

Import the real endpoint from its source AST to avoid loading unrelated API
modules that require optional authentication providers in the test runner.
"""
import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.driver_order_offer_models import DriverOrderOffer
from app.models import City, Order, OrderStatusHistory, User


def load_cancel_endpoint():
    path = Path(__file__).resolve().parents[1] / 'app/main.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'cancel_passenger_order')
    function.decorator_list = []
    namespace = {
        'UUID': UUID, 'User': User, 'Session': Session, 'Depends': lambda x: None,
        'get_current_passenger': lambda: None, 'get_db': lambda: None,
        'Order': Order, 'City': City, 'DriverOrderOffer': DriverOrderOffer,
        'OrderStatusHistory': OrderStatusHistory, 'select': select,
        'datetime': datetime, 'timezone': timezone, 'HTTPException': HTTPException,
        'OrderResponse': dict,
        'order_to_response': lambda order, city: {'id': str(order.id), 'status': order.status},
    }
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(module, str(path), 'exec'), namespace)
    return namespace['cancel_passenger_order']


@pytest.fixture()
def order_session():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            city = City(code='test-city', name='Тестовый город')
            owner = User(username=f'owner-{uuid4()}')
            stranger = User(username=f'stranger-{uuid4()}')
            db.add_all([city, owner, stranger])
            db.flush()
            yield db, city, owner, stranger
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def new_order(db, city, owner, status='new'):
    order = Order(
        city_id=city.id, passenger_user_id=owner.id,
        public_number=f'VEXA-{uuid4()}', customer_name='Клиент',
        customer_phone='+79990000000', pickup_address='A', destination_address='B',
        payment_method='cash', status=status, idempotency_key=str(uuid4()),
    )
    db.add(order)
    db.commit()
    return order


@pytest.mark.parametrize('initial_status', ['new', 'accepted'])
def test_owner_can_cancel_pending_order_idempotently(order_session, initial_status):
    db, city, owner, stranger = order_session
    order = new_order(db, city, owner, initial_status)
    endpoint = load_cancel_endpoint()
    response = endpoint(order.id, passenger=owner, db=db)
    assert response['status'] == 'cancelled'
    assert endpoint(order.id, passenger=owner, db=db)['status'] == 'cancelled'
    events = db.scalars(select(OrderStatusHistory).where(
        OrderStatusHistory.order_id == order.id)).all()
    assert len(events) == 1
    assert events[0].old_status == initial_status
    assert events[0].changed_by_user_id == owner.id


def test_stranger_cannot_cancel_or_see_order(order_session):
    db, city, owner, stranger = order_session
    order = new_order(db, city, owner)
    with pytest.raises(HTTPException) as error:
        load_cancel_endpoint()(order.id, passenger=stranger, db=db)
    assert error.value.status_code == 404
    db.refresh(order)
    assert order.status == 'new'


@pytest.mark.parametrize('state', ['assigned', 'arrived', 'in_progress', 'completed'])
def test_no_self_service_cancel_after_driver_assignment(order_session, state):
    db, city, owner, stranger = order_session
    order = new_order(db, city, owner, state)
    with pytest.raises(HTTPException) as error:
        load_cancel_endpoint()(order.id, passenger=owner, db=db)
    assert error.value.status_code == 409
    db.refresh(order)
    assert order.status == state


def test_pending_driver_offer_is_cancelled_together_with_order(order_session):
    db, city, owner, stranger = order_session
    order = new_order(db, city, owner, 'accepted')
    offer = DriverOrderOffer(
        order_id=order.id, driver_user_id=uuid4(), vehicle_id=uuid4(),
        status='pending', attempt_number=1,
        response_timeout_seconds=13,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=13),
    )
    db.add(offer)
    db.commit()
    load_cancel_endpoint()(order.id, passenger=owner, db=db)
    db.refresh(offer)
    assert offer.status == 'cancelled'
    assert offer.responded_at is not None


def test_mobile_cancel_requires_confirmation_and_authorized_request():
    root = Path(__file__).resolve().parents[2]
    api = (root / 'android/client/app/src/main/java/ru/vexa/client/ApiClient.kt').read_text()
    panel = (root / 'android/client/app/src/main/java/ru/vexa/client/PassengerOrderStatusPanel.kt').read_text()
    assert 'suspend fun cancelPassengerOrder(' in api
    assert '.header("Authorization", "Bearer $token")' in api
    assert '.addPathSegment("cancel")' in api
    assert 'confirmCancellation = true' in panel
    assert 'status == "new" || status == "accepted"' in panel
