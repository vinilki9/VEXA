"""Run with: python -m app.dispatch_worker (separate container/process)."""
import logging
import signal
from threading import Event
from pathlib import Path

from app.config import settings
from app.database import SessionLocal
from app.dispatch_engine import dispatch_tick

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("vexa.dispatch_worker")
stop_event = Event()


def main():
    signal.signal(signal.SIGINT, lambda *_: stop_event.set())
    signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
    heartbeat = Path("/tmp/vexa-dispatch-worker.heartbeat")
    heartbeat.unlink(missing_ok=True)
    logger.info("Dispatch worker started; poll=%.1fs timeout=%ds", settings.dispatch_poll_interval_seconds,
                settings.dispatch_search_timeout_seconds)
    while not stop_event.is_set():
        with SessionLocal() as db:
            try:
                result = dispatch_tick(db)
                heartbeat.touch()
                if result["started"] or result["offered"] or result["no_driver_found"]:
                    logger.info("Dispatch tick %s", result)
            except Exception:
                db.rollback()
                logger.exception("Dispatch worker tick failed")
        stop_event.wait(settings.dispatch_poll_interval_seconds)
    logger.info("Dispatch worker stopped")


if __name__ == "__main__":
    main()
