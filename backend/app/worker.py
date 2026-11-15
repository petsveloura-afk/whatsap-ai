"""Standalone worker/scheduler entrypoint for multi-instance deployments:  python -m app.worker
Run the API with WORKER_ENABLED=0 and one or more of these (jobs are claimed with SKIP LOCKED on Postgres, so N workers are safe).
On the free tier you can keep the default in-process worker instead (WORKER_ENABLED=1)."""
import logging, os, signal, time
from .db import SessionLocal
from . import main as _m  # noqa: F401  (loads models, wiring and handlers)
from . import jobqueue, routes_v2
log = logging.getLogger("sniper"); _stop = False
def _sig(*_):
    global _stop; _stop = True
def run(poll_s: float = 3.0, sched_s: float = 60.0, max_loops: int | None = None):
    signal.signal(signal.SIGTERM, _sig); signal.signal(signal.SIGINT, _sig); last = 0.0; loops = 0
    while not _stop and (max_loops is None or loops < max_loops):
        loops += 1
        try:
            with SessionLocal() as db: busy = jobqueue.run_once(db, routes_v2.HANDLERS)
            if time.monotonic() - last >= sched_s:
                with SessionLocal() as db: routes_v2.schedule_due(db)
                last = time.monotonic()
        except Exception as e: log.warning("worker loop error: %s", type(e).__name__); busy = False
        if not busy: time.sleep(poll_s)
if __name__ == "__main__":
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO")); run()
