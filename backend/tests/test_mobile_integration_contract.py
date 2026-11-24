"""Tests for the mobile/backend contract; no SMS or network credentials needed.

The selected FastAPI view is loaded from its AST because the complete application
imports optional authentication packages that are not present in every CI job.
The view itself is exercised against real SQLAlchemy tables in an in-memory DB.
"""

import ast
from pathlib import Path
from uuid import UUID, uuid4
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import City, Order, User

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'backend' / 'app' / 'main.py'
DRIVER = ROOT / 'backend' / 'app' / 'driver_api.py'


def function_from_source(path: Path, name: str):
    module = ast.parse(path.read_text(encoding='utf-8'))
    functions = [node for node in module.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
    assert len(functions) == 1, f'{path.name}: expected one {name}'
    return functions[0]


def load_passenger_view():
    function = function_from_source(BACKEND, 'get_passenger_order')
    # Compile the actual handler, without importing the rest of the FastAPI app.
    function.decorator_list = []
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    namespace = dict(
        User=User,
        Session=Session,
        Depends=lambda provider: None,
        get_current_passenger=lambda: None,
        get_db=lambda: None,
        UUID=UUID,
        HTTPException=HTTPException,
        Order=Order,
        City=City,
        select=select,
        order_to_response=lambda order, city: {
            'id': str(order.id),
            'public_number': order.public_number,
            'status': order.status,
            'city_code': city.code,
        },
    )
    exec(compile(module, str(BACKEND), 'exec'), namespace)
    return namespace['get_passenger_order']


def test_driver_status_parameter_is_a_uuid_not_string():
    node = function_from_source(DRIVER, 'update_driver_order_status')
    arg = next(arg for arg in node.args.args if arg.arg == 'order_id')
    assert isinstance(arg.annotation, ast.Name)
    assert arg.annotation.id == 'UUID'
    # Real DB bind processor: a str UUID fails for Uuid(as_uuid=True).
    engine = create_engine('sqlite://')
    processor = Order.__table__.c.id.type.bind_processor(engine.dialect)
    assert processor(uuid4())
    with pytest.raises(AttributeError):
        processor(str(uuid4()))
    engine.dispose()


def test_passenger_order_detail_respects_ownership_and_identifier():
    view = load_passenger_view()
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            city = City(code='obolensk', name='Оболенск')
            own = User(username='passenger_1')
            other = User(username='passenger_2')
            db.add_all([city, own, other])
            db.flush()
            order = Order(
                id=uuid4(), city_id=city.id, passenger_user_id=own.id,
                public_number='VEXA-OB-000125', customer_name='Пассажир',
                customer_phone='+79990000000', pickup_address='Адрес подачи',
                destination_address='Адрес назначения', status='assigned',
                payment_method='cash', idempotency_key='contract-1',
            )
            db.add(order)
            db.commit()
            assert view('VEXA-OB-000125', passenger=own, db=db)['status'] == 'assigned'
            assert view(str(order.id), passenger=own, db=db)['id'] == str(order.id)
            for user, identifier in [
                (other, 'VEXA-OB-000125'),
                (other, str(order.id)),
                (own, 'missing'),
                (own, 'x' * 81),
            ]:
                with pytest.raises(HTTPException) as error:
                    view(identifier, passenger=user, db=db)
                assert error.value.status_code == 404
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_android_uses_authenticated_detail_endpoint_instead_of_first_50():
    client_root = ROOT / 'android' / 'client'
    api = (client_root / 'app/src/main/java/ru/vexa/client/ApiClient.kt').read_text()
    panel = (client_root / 'app/src/main/java/ru/vexa/client/PassengerOrderStatusPanel.kt').read_text()
    assert 'fun getPassengerOrder(orderIdentifier: String)' in api
    assert '.header("Authorization", "Bearer $token")' in api
    assert '.addPathSegments("api/v1/passenger/orders")' in api
    assert 'ApiClient.getPassengerOrder(orderIdentifier)' in panel
    assert 'ApiClient.getPassengerOrders()' not in panel


def test_mobile_statuses_and_city_configuration_agree():
    driver_root = ROOT / 'android' / 'driver'
    client_root = ROOT / 'android' / 'client'
    driver_api = (driver_root / 'app/src/main/java/ru/vexa/driver/DriverApiClient.kt').read_text()
    backend = DRIVER.read_text()
    client_repo = (client_root / 'app/src/main/java/ru/vexa/client/PassengerOrderRepository.kt').read_text()
    assert '"arrived", "in_progress", "completed"' in driver_api
    assert '"assigned": "arrived"' in backend
    assert '"arrived": "in_progress"' in backend
    assert '"in_progress": "completed"' in backend
    assert 'BuildConfig.VEXA_CITY_CODE' in client_repo
    for app_root in (client_root, driver_root):
        build = (app_root / 'app/build.gradle.kts').read_text()
        assert '"vexaCityCode"' in build
        assert '"VEXA_CITY_CODE"' in build


def test_all_mobile_http_paths_exist_in_backend():
    import re
    kotlin_roots = [
        ROOT / 'android/client/app/src/main/java/ru/vexa/client/ApiClient.kt',
        ROOT / 'android/driver/app/src/main/java/ru/vexa/driver/DriverApiClient.kt',
    ]
    mobile_paths = []
    for source in kotlin_roots:
        text = source.read_text(encoding='utf-8')
        mobile_paths.extend(re.findall(
            r'(?:\.url\("\$BASE_URL|path\s*=\s*")(/api/v1/[^"\n]*)', text
        ))
    mobile_paths.append('/api/v1/passenger/orders/$orderIdentifier')
    backend_paths = []
    for backend_source in (ROOT / 'backend/app').glob('*.py'):
        tree = ast.parse(backend_source.read_text(encoding='utf-8'))
        prefix = '/api/v1/auth/passenger' if backend_source.name == 'passenger_auth.py' else ''
        for fn in tree.body:
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in fn.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                if decorator.func.attr not in {'get', 'post', 'put', 'patch', 'delete'}:
                    continue
                if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
                    route = prefix + decorator.args[0].value
                    if route.startswith('/api/v1/'):
                        backend_paths.append(route)
    missing = []
    for mobile_path in mobile_paths:
        parts = mobile_path.split('/')
        matching = False
        for backend_path in backend_paths:
            expected = backend_path.split('/')
            if len(parts) != len(expected):
                continue
            matching = all(a == b or a.startswith('$') or (b.startswith('{') and b.endswith('}'))
                           for a, b in zip(parts, expected))
            if matching:
                break
        if not matching:
            missing.append(mobile_path)
    assert not missing, f'Endpoints requested by Android missing on Backend: {missing}'
    assert len(mobile_paths) >= 20


def test_passenger_handles_expired_session_without_infinite_polling():
    client = (ROOT / 'android/client/app/src/main/java/ru/vexa/client/ApiClient.kt').read_text()
    panel = (ROOT / 'android/client/app/src/main/java/ru/vexa/client/PassengerOrderStatusPanel.kt').read_text()
    assert 'class ApiHttpException(val statusCode: Int' in client
    assert 'throw ApiHttpException(response.code, result)' in client
    assert 'private val DEFAULT_CITY_CODE = BuildConfig.VEXA_CITY_CODE' in client
    assert 'catch (error: ApiHttpException)' in panel
    assert 'error.statusCode == 401 || error.statusCode == 403' in panel
    assert 'authenticationError = true' in panel
    assert 'break // Повторный запрос' in panel
