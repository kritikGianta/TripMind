"""Background worker: runs scheduled jobs outside the API process.

    python -m app.worker

Each job runs on its own interval. Before a run the worker takes a lock in the shared store
(Redis in Docker), so with several workers, or a worker plus an API still running in-process
jobs, each run happens exactly once. Jobs are idempotent and commit their own work, so a crash
mid-run is safe: the lock expires and the next run continues. Metrics are served on
WORKER_METRICS_PORT for Prometheus.
"""

from __future__ import annotations

import signal
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from types import FrameType

import structlog
from prometheus_client import Counter, Gauge, Histogram, start_http_server

from app.core.config import Settings, get_settings
from app.core.deps import get_kv_store
from app.core.kv import KeyValueStore
from app.core.logging import configure_logging
from app.worker_jobs import JOBS

log = structlog.get_logger(__name__)

JOB_RUNS = Counter("worker_job_runs_total", "Worker job runs by outcome.", ["job", "outcome"])
JOB_DURATION = Histogram("worker_job_duration_seconds", "Worker job run time.", ["job"])
HEARTBEAT = Gauge("worker_heartbeat_timestamp_seconds", "Last time the worker loop ran.")


@dataclass
class Job:
    name: str
    interval_seconds: float
    run: Callable[[Settings], int]
    next_run: float = field(default=0.0)


class Worker:
    def __init__(self, settings: Settings, store: KeyValueStore, jobs: list[Job]) -> None:
        self._settings = settings
        self._store = store
        self._jobs = jobs
        self._stopping = False

    def stop(self, *_: object) -> None:
        log.info("worker_stopping")
        self._stopping = True

    def run_due(self, now: float) -> None:
        for job in self._jobs:
            if now < job.next_run:
                continue
            job.next_run = now + job.interval_seconds
            # The lock lasts slightly less than the interval, so a crashed run never blocks
            # the next one, and two workers never run the same job at once.
            if not self._store.set_if_absent(
                f"job:{job.name}", "running", job.interval_seconds * 0.9
            ):
                JOB_RUNS.labels(job=job.name, outcome="skipped_locked").inc()
                continue
            started = time.perf_counter()
            try:
                changed = job.run(self._settings)
                JOB_RUNS.labels(job=job.name, outcome="ok").inc()
                if changed:
                    log.info("job_done", job=job.name, changed=changed)
            except Exception:  # one failing job must not stop the others
                JOB_RUNS.labels(job=job.name, outcome="error").inc()
                log.exception("job_failed", job=job.name)
            finally:
                JOB_DURATION.labels(job=job.name).observe(time.perf_counter() - started)

    def loop(self, tick_seconds: float = 1.0) -> None:
        log.info("worker_started", jobs=[j.name for j in self._jobs])
        while not self._stopping:
            now = time.monotonic()
            self.run_due(now)
            HEARTBEAT.set_to_current_time()
            self._store.set("worker:heartbeat", str(time.time()), 120)
            time.sleep(tick_seconds)
        log.info("worker_stopped")


def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    start_http_server(settings.worker_metrics_port)
    worker = Worker(
        settings, get_kv_store(), [Job(name, interval, run) for name, interval, run in JOBS]
    )

    def _stop(signum: int, frame: FrameType | None) -> None:
        worker.stop()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    worker.loop()


if __name__ == "__main__":
    main()
