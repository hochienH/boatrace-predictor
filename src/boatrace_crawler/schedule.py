"""每日開催表：取得當天實際有開催的 jcd 清單。"""

from __future__ import annotations

import re
from datetime import date, datetime

from . import storage
from .config import JST, RACE_BASE, VENUES
from .fetcher import Fetcher

_JCD_RE = re.compile(rb"jcd=(\d{2})")


def today_jst() -> date:
    """日本當地的今天（開催日以 JST 為準，不能用本機時區的 date.today()）。"""
    return datetime.now(JST).date()


def index_url(hd: str) -> str:
    return f"{RACE_BASE}/index?hd={hd}"


def open_venues(fetcher: Fetcher, hd: str, refresh: bool = False) -> list[str]:
    """回傳當日開催的 jcd（已排序）。索引頁會快取到 data/raw/index。"""
    path = storage.index_path(hd)
    if path.exists() and not refresh:
        html = storage.read_gzip(path)
    else:
        url = index_url(hd)
        html = fetcher.get(url)
        storage.write_gzip(path, html)
        storage.record("index", url, "ok", hd=hd, bytes=len(html))

    found = {m.decode() for m in _JCD_RE.findall(html)}
    return sorted(found & VENUES.keys())
