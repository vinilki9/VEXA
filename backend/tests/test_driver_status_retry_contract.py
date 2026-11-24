"""Integration-like SQLite tests of the real driver status handler without optional JWT packages."""
import ast
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import City, Order, OrderStatusHistory, User, Vehicle

ROOT = Path(__file__).resolve().parents[2]


def load_status_handler(finance_events, city_id):
    path = ROOT / 'backend/app/driver_api.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    func = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == 'update_driver_order_status')
    func.decorator_list = []
    namespace = {
        'UUID': UUID, 'User': User, 'Session': Session, 'Depends': lambda x: None,
        'get_current_driver': lambda: None, 'get_db': lambda: None,
        'get_driver_profile': lambda db, user: SimpleNamespace(city_id=city_id),
        'Order': Order, 'Vehicle': Vehicle, 'OrderStatusHistory': OrderStatusHistory,
        'DriverOrderStatusRequest': SimpleNamespace, 'select': select,
        'HTTPException': HTTPException, 'datetime': datetime, 'timezone': timezone,
        'DRIVER_ORDER_STATUS_TRANSITIONS': {
            'assigned': 'arrived', 'arrived': 'in_progress', 'in_progress': 'completed',
        },
        'create_completed_trip_finance': lambda **kwargs: finance_events.append(kwargs['order'].id),
        'driver_order_response': lambda order, vehicle: {'id': str(order.id), 'status': order.status},
    }
    code = ast.fix_missing_locations(ast.Module(body=[func], type_ignores=[]))
    exec(compile(code, str(path), 'exec'), namespace)
    return namespace['update_driver_order_status']


@pytest.mark.parametrize('old,new', [('assigned', 'arrived'), ('arrived', 'in_progress'), ('in_progress', 'completed')])
def test_retried_status_does_not_duplicate_history_or_finance(old, new):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            city = City(code='test-city', name='Тестовый город')
            driver = User(username='driver-test')
            db.add_all([city, driver])
            db.flush()
            order = Order(id=uuid4(), city_id=city.id, driver_user_id=driver.id,
                          public_number='VEXA-TEST', customer_name='Клиент',
                          customer_phone='+79990000000', pickup_address='A',
                          destination_address='B', payment_method='cash', status=old,
                          idempotency_key=f'contract-{old}-{new}')
            db.add(order)
            db.commit()
            finance_events = []
            view = load_status_handler(finance_events, city.id)
            first = view(order.id, SimpleNamespace(status=new), driver=driver, db=db)
            second = view(order.id, SimpleNamespace(status=new), driver=driver, db=db)
            assert first['order']['status'] == new
            assert second['success'] is True
            assert second['message'] == 'Статус уже установлен'
            assert db.scalar(select(func.count()).select_from(OrderStatusHistory)
                             .where(OrderStatusHistory.order_id == order.id)) == 1
            assert len(finance_events) == (1 if new == 'completed' else 0)
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_android_driver_invalidates_offer_cache_on_actions_and_account_switch():
    source = (ROOT / 'android/driver/app/src/main/java/ru/vexa/driver/DriverApiClient.kt').read_text()
    assert 'if (accessToken != normalizedToken)' in source
    assert 'clearCachedOrderOffers()' in source.split('fun setAccessToken(token: String)')[1].split('fun getAccessToken()')[0]
    for action in ('acceptOrderOffer', 'rejectOrderOffer'):
        body = source.split('fun ' + action + '(')[1].split('fun ', 1)[0]
        assert 'finally' in body
        assert 'clearCachedOrderOffers()' in body
