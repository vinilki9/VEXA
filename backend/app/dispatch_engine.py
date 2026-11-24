"""VEXA automatic dispatch service, run only by the separate worker process.

The database is the queue of truth. A new order is never dependent on an
in-memory task, and a restart recovers orders left in new/accepted states.
PostgreSQL order locks allow more than one worker, though normally one is enough.
"""
from datetime import datetime, timezone
import logging

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.dispatch_order_api import (
    NO_AVAILABLE_DRIVERS_MESSAGE,
    create_next_driver_offer,
    normalize_datetime,
    process_expired_driver_offers,
)
from app.driver_order_offer_models import DriverOrderOffer
from app.models import Order, OrderStatusHistory
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def mark_no_driver_found(db: Session, order: Order, now: datetime) -> bool:
    """Terminal, non-billable result; old offers cannot be accepted afterwards."""
    old_status = order.status
    if old_status != "accepted" or order.driver_user_id is not None:
        return False
    # All live offers must finish before a search is declared unsuccessful.
    live_offer = db.scalar(select(DriverOrderOffer.id).where(
        DriverOrderOffer.order_id == order.id,
        DriverOrderOffer.status == "pending",
        DriverOrderOffer.expires_at > now,
    ).limit(1))
    if live_offer is not None:
        return False
    order.status = "no_driver_found"
    order.updated_at = now
    db.add(OrderStatusHistory(
        order_id=order.id, old_status=old_status,
        new_status="no_driver_found", changed_by_user_id=None,
    ))
    db.commit()
    return True


def process_automatic_dispatch(db: Session, limit: int | None = None, *, now: datetime | None = None) -> dict:
    """Process at most `limit` unassigned orders. Idempotent on every poll.

    If no eligible driver currently exists, keep searching for a bounded
    window; do not burn through duplicate offers to the same driver.
    """
    now = now or datetime.now(timezone.utc)
    batch_size = settings.dispatch_batch_size if limit is None else limit
    pending_live = exists(select(DriverOrderOffer.id).where(
        DriverOrderOffer.order_id == Order.id,
        DriverOrderOffer.status == "pending",
        DriverOrderOffer.expires_at > now,
    ))
    order_ids = db.scalars(
        select(Order.id).where(
            or_(Order.status == "new", and_(Order.status == "accepted", ~pending_live)),
            Order.driver_user_id.is_(None),
        ).order_by(Order.created_at, Order.id).limit(batch_size)
    ).all()
    stats = {"scanned": 0, "started": 0, "offered": 0, "waiting": 0, "no_driver_found": 0}
    for order_id in order_ids:
        try:
            # Consistent lock order: ORDER first, OFFER second, like Driver accept/cancel.
            order = db.scalar(select(Order).where(Order.id == order_id)
                              .with_for_update(skip_locked=True))
            if order is None or order.status not in ("new", "accepted") or order.driver_user_id is not None:
                db.rollback()
                continue
            stats["scanned"] += 1
            if order.status == "new":
                order.status = "accepted"
                order.updated_at = now
                db.add(OrderStatusHistory(
                    order_id=order.id, old_status="new", new_status="accepted",
                    changed_by_user_id=None,
                ))
                stats["started"] += 1
            deadline_exceeded = (now - normalize_datetime(order.created_at)).total_seconds() >= settings.dispatch_search_timeout_seconds
            # Running offer is never cancelled by search timeout alone.
            if deadline_exceeded:
                db.flush()
                if mark_no_driver_found(db, order, now):
                    stats["no_driver_found"] += 1
                continue
            try:
                result = create_next_driver_offer(db=db, order=order)
                if result.get("offered"):
                    stats["offered"] += 1
                else:
                    stats["waiting"] += 1
            except HTTPException as exc:
                if exc.status_code != 409 or exc.detail != NO_AVAILABLE_DRIVERS_MESSAGE:
                    raise
                # create_next_driver_offer committed the order state and exhausted offers.
                stats["waiting"] += 1
        except IntegrityError:
            # A second worker may try offering the same driver concurrently.
            # Database partial unique index protects from duplicate live offers.
            db.rollback()
            logger.info("Dispatch concurrency conflict for order %s; retry on next tick", order_id)
        except Exception:
            db.rollback()
            logger.exception("Dispatch failed for order %s", order_id)
        finally:
            # create_next_driver_offer commits its own transaction; no order lock
            # should remain held between separate order iterations.
            if db.in_transaction():
                db.rollback()
    return stats


def dispatch_tick(db: Session, *, now: datetime | None = None) -> dict:
    expired = process_expired_driver_offers(db, limit=settings.dispatch_batch_size, advance_to_next=False)
    counts = process_automatic_dispatch(db, now=now)
    return {"expired_handled": expired, **counts}
