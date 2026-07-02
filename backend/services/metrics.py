from datetime import datetime
from typing import Optional
import time

_record_registry = {}


def record(key: str, duration: float):
    """Internal: accumulate raw durations in an in-memory registry."""
    if key not in _record_registry:
        _record_registry[key] = []
    _record_registry[key].append(duration)


def get_records(key: str) -> list[float]:
    return _record_registry.get(key, [])


def reset_records(key: str):
    _record_registry.pop(key, None)


def report() -> dict[str, float]:
    return {k: sum(v) for k, v in _record_registry.items()}


class Timer:
    def __init__(self, key: str):
        self.key = key
        self._start_time: float | None = None

    def start(self):
        self._start_time = time.time()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        if self._start_time is not None:
            record(self.key, time.time() - self._start_time)

    @property
    def elapsed(self) -> float:
        if self._start_time is None:
            raise RuntimeError(f"Timer '{self.key}' was never started (use `with Timer(...)` or call .start)")
        return time.time() - self._start_time
