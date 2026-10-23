"""每日開催表：取得當天實際有開催的 jcd 清單，以及各場的 締切予定時刻。"""

from __future__ import annotations

import re
from datetime import date, datetime

from . import storage
from .config import JST, RACE_BASE, RACES_PER_DAY, VENUES
from .fetcher import Fetcher

_JCD_RE = re.compile(rb"jcd=(\d{2})")

# 賽事頁（odds3t / pcexpect / racelist…）上方的導覽表有一列「締切予定時刻」，後面接 12 個 <td>HH:MM</td>。
# 發售前的「データはありません」頁也有這張表（2026-10-23 JST 00:02 的快照已含全日時刻）。
_DEADLINE_ROW_RE = re.compile("締切予定時刻".encode() + rb"</t[dh]>(.*?)</tr>", re.S)
_DEADLINE_TD_RE = re.compile(rb"<td[^>]*>\s*(\d{1,2}):(\d{2})\s*</td>")

Deadlines = dict[int, str]  # rno -> "HH:MM"（JST）


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


def parse_deadlines(body: bytes) -> Deadlines:
    """從賽事頁導覽表解出 12 場的 締切予定時刻；解不到剛好 12 個（頁面無表、部分場次中止顯示「-」）就回空 dict。"""
    m = _DEADLINE_ROW_RE.search(body)
    if not m:
        return {}
    times = [f"{int(h):02d}:{mm.decode()}" for h, mm in _DEADLINE_TD_RE.findall(m.group(1))]
    if len(times) != RACES_PER_DAY:
        return {}
    return dict(enumerate(times, start=1))


def deadline_at(hd: str, hhmm: str) -> datetime:
    """hd 當天 JST 的 HH:MM（timezone-aware）。"""
    return datetime.strptime(f"{hd} {hhmm}", "%Y%m%d %H:%M").replace(tzinfo=JST)


def load_deadlines(hd: str) -> dict[str, Deadlines]:
    """讀當日締切時刻快取 {jcd: {rno: "HH:MM"}}；沒有或壞掉就空 dict。"""
    raw = storage.read_json(storage.deadlines_path(hd))
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Deadlines] = {}
    for jcd, table in raw.items():
        if not isinstance(table, dict):
            continue
        try:
            out[str(jcd)] = {int(rno): str(t) for rno, t in table.items()}
        except ValueError:
            continue
    return out


def save_deadlines(hd: str, table: dict[str, Deadlines]) -> None:
    storage.write_json(
        storage.deadlines_path(hd),
        {jcd: {str(rno): t for rno, t in sorted(d.items())} for jcd, d in sorted(table.items())},
    )
