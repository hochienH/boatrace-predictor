"""ボートレーサー検索：profile / back3 / season / course。"""

from __future__ import annotations

from collections import Counter

from . import storage
from .config import RACER_BASE, RACER_PREFIXES
from .fetcher import Fetcher, FetchError
from .parallel import run_tasks

_MARKER = b"racer1_image"


def racer_url(prefix: str, toban: int) -> str:
    return f"{RACER_BASE}/{prefix}?toban={toban:04d}"


def _fetch_page(fetcher: Fetcher, toban: int, prefix: str, overwrite: bool) -> str | None:
    """回傳 outcome；None 代表該登録番号不存在。"""
    path = storage.racer_path(toban, prefix)
    if path.exists() and not overwrite:
        return "skip"
    url = racer_url(prefix, toban)
    try:
        body = fetcher.get(url)
    except FetchError:
        storage.record("racer", url, "failed")
        return "failed"
    if _MARKER not in body:
        storage.record("racer", url, "empty")
        return None
    storage.write_gzip(path, body)
    storage.record("racer", url, "ok", bytes=len(body))
    return "ok"


def _fetch_racer(fetcher: Fetcher, toban: int, overwrite: bool) -> str:
    # 先探 profile，不存在就不必再打其餘三頁（絕大多數 toban 是空號）。
    head = _fetch_page(fetcher, toban, "profile", overwrite)
    if head is None:
        return "absent"
    outcomes = [head]
    for prefix in RACER_PREFIXES[1:]:
        result = _fetch_page(fetcher, toban, prefix, overwrite)
        outcomes.append("empty" if result is None else result)
    if all(o == "skip" for o in outcomes):
        return "skip"
    return "failed" if "failed" in outcomes else "ok"


def crawl_racers(
    fetcher: Fetcher,
    start: int,
    end: int,
    workers: int = 5,
    overwrite: bool = False,
) -> Counter[str]:
    tobans = list(range(start, end + 1))
    print(f"racer: toban {start:04d}-{end:04d}（{len(tobans)} 個）")
    return run_tasks(
        tobans,
        lambda t: _fetch_racer(fetcher, t, overwrite),
        workers=workers,
        label="racer",
    )
