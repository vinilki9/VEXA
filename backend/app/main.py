from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.config import settings
from app.database import Base, engine, get_db
from app.models import Dispatcher, Order
from app.schemas import LoginIn, TokenOut, DispatcherOut, OrderCreate, OrderOut, OrderStatusUpdate
from app.security import verify_password, create_access_token, get_current_dispatcher

app = FastAPI(title=settings.app_name, version="0.1.0")
# Для стартового прототипа. В production заменить управлением схемой через Alembic.
Base.metadata.create_all(bind=engine)

@app.get("/health")
def health():
    return {"status": "ok", "service": "vexa-backend"}

@app.post("/api/dispatcher/auth/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    dispatcher = db.query(Dispatcher).filter(Dispatcher.username == data.username).first()
    if not dispatcher or not dispatcher.is_active or not verify_password(data.password, dispatcher.password_hash):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    return TokenOut(access_token=create_access_token(dispatcher.id))

@app.get("/api/dispatcher/auth/me", response_model=DispatcherOut)
def me(dispatcher: Dispatcher = Depends(get_current_dispatcher)):
    return dispatcher

@app.get("/api/dispatcher/orders", response_model=list[OrderOut])
def list_orders(
    city_id: str = Query(default="obolensk"),
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    dispatcher: Dispatcher = Depends(get_current_dispatcher),
):
    query = db.query(Order).filter(Order.city_id == city_id)
    if status:
        query = query.filter(Order.status == status)
    return query.order_by(Order.created_at.desc()).offset(offset).limit(limit).all()

@app.post("/api/dispatcher/orders", response_model=OrderOut, status_code=201)
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    dispatcher: Dispatcher = Depends(get_current_dispatcher),
):
    allowed_payments = {"cash", "transfer", "card", "sbp"}
    if data.payment_method not in allowed_payments:
        raise HTTPException(status_code=422, detail="Недопустимый способ оплаты")
    order = Order(**data.model_dump(), status="new")
    db.add(order)
    db.commit()
    db.refresh(order)
    return order

@app.patch("/api/dispatcher/orders/{order_id}/status", response_model=OrderOut)
def update_order_status(
    order_id: int,
    data: OrderStatusUpdate,
    db: Session = Depends(get_db),
    dispatcher: Dispatcher = Depends(get_current_dispatcher),
):
    allowed = {"new", "searching_driver", "driver_assigned", "driver_arriving",
               "driver_arrived", "in_trip", "completed", "cancelled"}
    if data.status not in allowed:
        raise HTTPException(status_code=422, detail="Неизвестный статус заказа")
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    order.status = data.status
    order.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(order)
    return order

@app.get("/api/dispatcher/summary")
def summary(
    city_id: str = Query(default="obolensk"),
    db: Session = Depends(get_db),
    dispatcher: Dispatcher = Depends(get_current_dispatcher),
):
    total = db.query(func.count(Order.id)).filter(Order.city_id == city_id).scalar() or 0
    active_statuses = ["new", "searching_driver", "driver_assigned", "driver_arriving",
                       "driver_arrived", "in_trip"]
    active = db.query(func.count(Order.id)).filter(
        Order.city_id == city_id, Order.status.in_(active_statuses)
    ).scalar() or 0
    completed = db.query(func.count(Order.id)).filter(
        Order.city_id == city_id, Order.status == "completed"
    ).scalar() or 0
    return {"city_id": city_id, "orders_total": total, "orders_active": active,
            "orders_completed": completed}
