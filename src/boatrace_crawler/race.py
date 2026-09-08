"""賽事頁面爬取：racelist / beforeinfo / raceresult / odds* / pcexpect。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from . import schedule, storage
from .config import RACE_BASE, RACE_PREFIXES, RACES_PER_DAY
from .fetcher import Fetcher, FetchError
from .parallel import run_tasks

# 未開催／尚未產生的頁面會回一個沒有資料表的通用外框頁。
_TABLE_MARKER = b'class="table1'


@dataclass(frozen=True, slots=True)
class RaceTask:
    hd: str
    jcd: str
    rno: int
    prefix: str

    @property
    def url(self) -> str:
        return f"{RACE_BASE}/{self.prefix}?rno={self.rno}&jcd={self.jcd}&hd={self.hd}"


def date_range(start: str, end: str) -> list[str]:
    d0 = date.fromisoformat(f"{start[:4]}-{start[4:6]}-{start[6:]}")
    d1 = date.fromisoformat(f"{end[:4]}-{end[4:6]}-{end[6:]}")
    if d1 < d0:
        raise ValueError(f"end {end} 早於 start {start}")
    return [(d0 + timedelta(days=i)).strftime("%Y%m%d") for i in range((d1 - d0).days + 1)]


def _fetch_one(fetcher: Fetcher, task: RaceTask, overwrite: bool) -> str:
    path = storage.race_path(task.hd, task.jcd, task.prefix, task.rno)
    if path.exists() and not overwrite:
        return "skip"
    try:
        body = fetcher.get(task.url)
    except FetchError:
        storage.record("race", task.url, "failed")
        return "failed"
    if _TABLE_MARKER not in body:
        storage.record("race", task.url, "empty")
        return "empty"
    storage.write_gzip(path, body)
    storage.record("race", task.url, "ok", bytes=len(body))
    return "ok"


def crawl_dates(
    fetcher: Fetcher,
    dates: list[str],
    prefixes: tuple[str, ...] = RACE_PREFIXES,
    workers: int = 5,
    overwrite: bool = False,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for hd in dates:
        venues = schedule.open_venues(fetcher, hd)
        if not venues:
            print(f"{hd}: 無開催")
            continue
        tasks = [
            RaceTask(hd, jcd, rno, prefix)
            for jcd in venues
            for rno in range(1, RACES_PER_DAY + 1)
            for prefix in prefixes
        ]
        print(f"{hd}: {len(venues)} 場 / {len(tasks)} 頁")
        counts += run_tasks(
            tasks,
            lambda t: _fetch_one(fetcher, t, overwrite),
            workers=workers,
            label=hd,
        )
    return counts
