"""HTTP 取得層：thread-local session、重試退避、失敗時全域降速。"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter

from .config import (
    COOLDOWN_BASE,
    COOLDOWN_MAX,
    DEFAULT_DELAY,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    DEFAULT_WORKERS,
    USER_AGENT,
)

_local = threading.local()


class FetchError(RuntimeError):
    pass


class _Circuit:
    """連續失敗時讓所有 worker 一起停一下，避免持續對站台加壓。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._resume_at = 0.0
        self._streak = 0

    def wait(self) -> None:
        while True:
            with self._lock:
                remaining = self._resume_at - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(remaining, 1.0))

    def on_success(self) -> None:
        with self._lock:
            self._streak = 0

    def on_failure(self) -> None:
        with self._lock:
            self._streak += 1
            if self._streak >= 5:
                pause = min(COOLDOWN_BASE * 2 ** (self._streak - 5), COOLDOWN_MAX)
                self._resume_at = max(self._resume_at, time.monotonic() + pause)


_circuit = _Circuit()


def _session(pool_size: int) -> requests.Session:
    sess = getattr(_local, "session", None)
    if sess is None:
        sess = requests.Session()
        sess.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "ja,en;q=0.8",
            }
        )
        adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size)
        sess.mount("https://", adapter)
        sess.mount("http://", adapter)
        _local.session = sess
    return sess


@dataclass(slots=True)
class Fetcher:
    delay: float = DEFAULT_DELAY
    timeout: float = DEFAULT_TIMEOUT
    retries: int = DEFAULT_RETRIES
    pool_size: int = DEFAULT_WORKERS

    def get(self, url: str) -> bytes:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            _circuit.wait()
            if self.delay:
                time.sleep(self.delay * random.uniform(0.8, 1.2))
            try:
                resp = _session(self.pool_size).get(url, timeout=self.timeout)
            except requests.RequestException as exc:
                last_error = exc
            else:
                if resp.status_code == 200:
                    _circuit.on_success()
                    return resp.content
                if resp.status_code == 404:
                    _circuit.on_success()
                    raise FetchError(f"404 {url}")
                last_error = FetchError(f"HTTP {resp.status_code} {url}")
            _circuit.on_failure()
            time.sleep((2**attempt) * 1.0 + random.uniform(0, 0.5))
        raise FetchError(f"failed after {self.retries} attempts: {url}") from last_error

    def get_text(self, url: str, encoding: str = "utf-8") -> str:
        return self.get(url).decode(encoding, errors="replace")
