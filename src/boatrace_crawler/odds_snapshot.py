"""締切前賠率時系列快照：定時對當天開催中賽事的三連単賠率頁存檔（不覆蓋，累積時間序列）。

官方只保留締切那一刻的定格賠率（見 race.py 的歷史回補），這裡補的是締切前的變動軌跡——
歷史無法回補，只能從現在起持續累積（REVIEW.md §3.5、develop-plan-1.md）。
設計成一次性函式，交給 scripts/run_odds_snapshot.sh 每隔固定秒數呼叫一次（cron 式輪詢）。
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass

from . import schedule, storage
from .config import RACE_BASE, RACES_PER_DAY, SNAPSHOT_PREFIXES
from .fetcher import Fetcher, FetchError
from .parallel import run_tasks

_TABLE_MARKER = b'class="table1'


@dataclass(frozen=True, slots=True)
class SnapshotTask:
    hd: str
    jcd: str
    rno: int
    prefix: str
    ts: int

    @property
    def url(self) -> str:
        return f"{RACE_BASE}/{self.prefix}?rno={self.rno}&jcd={self.jcd}&hd={self.hd}"


def _fetch_one(fetcher: Fetcher, task: SnapshotTask) -> str:
    try:
        body = fetcher.get(task.url)
    except FetchError:
        storage.record("odds_snapshot", task.url, "failed", ts=task.ts)
        return "failed"
    if _TABLE_MARKER not in body:
        storage.record("odds_snapshot", task.url, "empty", ts=task.ts)
        return "empty"
    path = storage.snapshot_path(task.hd, task.jcd, task.prefix, task.rno, task.ts)
    storage.write_gzip(path, body)
    storage.record("odds_snapshot", task.url, "ok", ts=task.ts, bytes=len(body))
    return "ok"


def snapshot_once(
    fetcher: Fetcher,
    hd: str | None = None,
    prefixes: tuple[str, ...] = SNAPSHOT_PREFIXES,
    workers: int = 20,
) -> Counter[str]:
    """對某日目前開催中的所有場次拍一次賠率快照。"""
    hd = hd or schedule.today_jst().strftime("%Y%m%d")
    venues = schedule.open_venues(fetcher, hd)
    if not venues:
        print(f"{hd}: 無開催，略過")
        return Counter()
    ts = int(time.time())
    tasks = [
        SnapshotTask(hd, jcd, rno, prefix, ts)
        for jcd in venues
        for rno in range(1, RACES_PER_DAY + 1)
        for prefix in prefixes
    ]
    return run_tasks(tasks, lambda t: _fetch_one(fetcher, t), workers=workers, label=f"snapshot:{hd}")
