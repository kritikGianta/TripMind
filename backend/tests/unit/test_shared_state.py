"""Shared state (in-memory and Redis), store-backed rate limits, and the worker's job locks."""

from __future__ import annotations

import fakeredis
import pytest

from app.core.config import Settings
from app.core.kv import FailOpenStore, InMemoryStore, KeyValueStore, RedisStore
from app.core.rate_limit import StoreRateLimiter
from app.worker import Job, Worker


@pytest.fixture(params=["memory", "redis"])
def store(request: pytest.FixtureRequest) -> KeyValueStore:
    if request.param == "memory":
        return InMemoryStore()
    return RedisStore("redis://unused", client=fakeredis.FakeRedis(decode_responses=True))


def test_values_locks_and_windows(store: KeyValueStore) -> None:
    store.set("a", "1", 60)
    assert store.get("a") == "1" and store.get("missing") is None
    assert store.set_if_absent("lock", "x", 60) is True
    assert store.set_if_absent("lock", "y", 60) is False  # second claimant loses
    store.delete("lock")
    assert store.set_if_absent("lock", "y", 60) is True
    results = [store.window_hit("ip", limit=3, window_seconds=60) for _ in range(4)]
    assert [allowed for allowed, _ in results] == [True, True, True, False]
    assert results[-1][1] >= 1  # retry-after is given
    assert store.ping()


def test_rate_limiter_is_shared_between_replicas() -> None:
    redis = fakeredis.FakeRedis(decode_responses=True)
    replica_a = StoreRateLimiter(RedisStore("redis://unused", client=redis))
    replica_b = StoreRateLimiter(RedisStore("redis://unused", client=redis))
    assert replica_a.hit("login:1.2.3.4", limit=2, window_seconds=60)[0]
    assert replica_b.hit("login:1.2.3.4", limit=2, window_seconds=60)[0]
    assert not replica_a.hit("login:1.2.3.4", limit=2, window_seconds=60)[0]


def test_redis_outage_fails_open_for_limits_and_closed_for_locks() -> None:
    class Down:
        def __getattr__(self, name: str) -> object:
            def fail(*args: object, **kwargs: object) -> object:
                raise ConnectionError("redis down")

            return fail

    store = FailOpenStore(Down())  # type: ignore[arg-type]
    assert store.window_hit("ip", limit=1, window_seconds=60) == (True, 0)  # keep serving
    assert store.get("x") is None and not store.ping()
    assert store.set_if_absent("job:x", "1", 60) is False  # never run a job twice


def test_worker_runs_each_job_once_across_workers() -> None:
    shared = InMemoryStore()
    runs: list[str] = []

    def job(settings: Settings) -> int:
        runs.append("ran")
        return 1

    settings = Settings(_env_file=None, environment="test")
    a = Worker(settings, shared, [Job("expire", 30, job)])
    b = Worker(settings, shared, [Job("expire", 30, job)])
    a.run_due(now=100.0)
    b.run_due(now=100.0)  # same moment, second worker: the lock is held
    assert runs == ["ran"]

    def broken(settings: Settings) -> int:
        raise RuntimeError("boom")

    c = Worker(settings, InMemoryStore(), [Job("broken", 30, broken), Job("ok", 30, job)])
    c.run_due(now=0.0)  # a failing job does not stop the others
    assert runs == ["ran", "ran"]
