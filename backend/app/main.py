from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime, timezone
from typing import Literal

app = FastAPI(title="VEXA API Starter", version="0.2.0")

TARIFFS = {
    "moscow": [
        {"code":"economy","name":"Economy","base_kopecks":15000,"included_minutes":3,"included_km":1,"per_km_kopecks":1300,"per_minute_kopecks":1300},
        {"code":"comfort","name":"Comfort","base_kopecks":18000,"included_minutes":3,"included_km":1,"per_km_kopecks":1500,"per_minute_kopecks":1500},
        {"code":"comfort_plus","name":"Comfort+","base_kopecks":21000,"included_minutes":3,"included_km":1,"per_km_kopecks":1800,"per_minute_kopecks":1800},
        {"code":"business","name":"Business","base_kopecks":41000,"included_minutes":3,"included_km":1,"per_km_kopecks":2500,"per_minute_kopecks":2500},
        {"code":"premier","name":"Premier","base_kopecks":65000,"included_minutes":8,"included_km":2,"per_km_kopecks":4100,"per_minute_kopecks":4100},
    ],
    "moscow_region": [
        {"code":"economy","name":"Economy","base_kopecks":15000,"included_minutes":3,"included_km":1,"per_km_kopecks":1300,"per_minute_kopecks":800},
        {"code":"comfort","name":"Comfort","base_kopecks":18000,"included_minutes":3,"included_km":1,"per_km_kopecks":1500,"per_minute_kopecks":1500},
        {"code":"comfort_plus","name":"Comfort+","base_kopecks":20000,"included_minutes":3,"included_km":1,"per_km_kopecks":1800,"per_minute_kopecks":1800},
        {"code":"business","name":"Business","base_kopecks":40000,"included_minutes":3,"included_km":1,"per_km_kopecks":2300,"per_minute_kopecks":2300},
        {"code":"premier","name":"Premier","base_kopecks":50000,"included_minutes":8,"included_km":2,"per_km_kopecks":4000,"per_minute_kopecks":4000},
    ],
}

class DemoOrder(BaseModel):
    organization_id: str
    branch_id: str
    passenger_phone: str = Field(min_length=5, max_length=32)
    pickup: str = Field(min_length=2, max_length=250)
    destination: str = Field(min_length=2, max_length=250)
    tariff_code: str
    payment_method: Literal["cash", "driver_transfer", "card", "sbp"] = "cash"
    anonymous: bool = False
    child_seat: bool = False
    animal: bool = False

@app.get("/health")
def health():
    return {"status":"demo", "service":"vexa-api", "utc":datetime.now(timezone.utc).isoformat()}

@app.get("/api/v1/tariffs/{city_group}")
def tariffs(city_group: str):
    if city_group not in TARIFFS:
        raise HTTPException(404, "Unknown demo city group")
    return {"city_group":city_group, "currency":"RUB", "tariffs":TARIFFS[city_group]}

@app.post("/api/v1/orders", status_code=202)
def create_demo_order(payload: DemoOrder, idempotency_key: str = Header(default="")):
    # Demonstration only: no persistence, driver dispatch, fare calculation or payment.
    if not idempotency_key:
        raise HTTPException(400, "Idempotency-Key header is required")
    if payload.tariff_code not in {x["code"] for x in TARIFFS["moscow"]}:
        raise HTTPException(400, "Unknown demo tariff")
    return {
        "demo": True,
        "order_id": str(uuid4()),
        "status": "demo_received",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "notice": "Демонстрационный ответ: заказ не сохранён и водитель не назначен."
    }
