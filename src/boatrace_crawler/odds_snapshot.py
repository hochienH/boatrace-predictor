"""締切前時系列快照：定時對當天開催中賽事的頁面存檔（不覆蓋，累積時間序列）。

官方只保留締切那一刻的定格賠率（見 race.py 的歷史回補），這裡補的是締切前的變動軌跡——
歷史無法回補，只能從現在起持續累積（REVIEW.md §3.5、develop-plan-1.md）。
目前抓兩種頁（config.SNAPSHOT_PREFIXES）：
- odds3t：每輪都落檔。
- pcexpect：コンピューター予想，只在內容變動時落檔（docs/decisions.md #4）；沒變的那一輪
  仍寫一筆 outcome=unchanged 到 manifest，之後才能知道「予想是在哪兩輪之間改的」。
  「內容」只看予想本體（_DEDUP_REGIONS）：頁面上方的 レース／締切予定時刻 導覽表會隨當日進行
  移動 is-activeColor1 之類的 class，整頁比對一天會誤判約 20 次（2026-10-23 用 odds3t 快照實測）。
  標記找不到（官方改版）就退回整頁比對，manifest 的 scope 欄位會變成 full，之後查得出來。
設計成一次性函式，交給 scripts/run_odds_snapshot.sh 每隔固定秒數呼叫一次（cron 式輪詢）。
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass

from . import schedule, storage
from .config import RACE_BASE, RACES_PER_DAY, SNAPSHOT_DEDUP_PREFIXES, SNAPSHOT_PREFIXES
from .fetcher import Fetcher, FetchError
from .parallel import run_tasks

_TABLE_MARKER = b'class="table1'
_KIND = "odds_snapshot"


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


# 去重時只比對這個區段：pcexpect 從「予選 1800m」標題區塊起到 </main> 為止，
# 涵蓋 予想フォーカス／自信度／進入予想 表與靜態注記，排除上方會隨時間變動的導覽表與頁首頁尾。
_DEDUP_REGIONS: dict[str, tuple[bytes, bytes]] = {
    "pcexpect": (b'<div class="title16__add2020">', b"</main>"),
}


def _dedup_hash(prefix: str, body: bytes) -> tuple[str, str]:
    """回傳 (hash, scope)；scope 是 region（切到本體）或 full（標記找不到、退回整頁）。"""
    region = _DEDUP_REGIONS.get(prefix)
    if region is None:
        return storage.content_hash(body), "full"
    payload, found = storage.extract_region(body, *region)
    return storage.content_hash(payload), ("region" if found else "full")


def _latest_hash(task: SnapshotTask) -> str | None:
    """同場次上一張快照的內容 hash；沒有舊檔、或舊檔讀不出來（gzip/zlib 壞掉皆算）就 None，視同有變動。"""
    latest = storage.latest_snapshot(task.hd, task.jcd, task.prefix, task.rno)
    if latest is None:
        return None
    try:
        return _dedup_hash(task.prefix, storage.read_gzip(latest))[0]
    except Exception:  # noqa: BLE001 — zlib.error 不是 OSError，任何讀取失敗都只該讓這輪重新落檔
        return None


def _fetch_one(fetcher: Fetcher, task: SnapshotTask) -> str:
    try:
        body = fetcher.get(task.url)
    except FetchError:
        storage.record(_KIND, task.url, "failed", ts=task.ts)
        return "failed"
    if _TABLE_MARKER not in body:
        storage.record(_KIND, task.url, "empty", ts=task.ts)
        return "empty"

    extra: dict[str, object] = {"ts": task.ts, "bytes": len(body)}
    if task.prefix in SNAPSHOT_DEDUP_PREFIXES:
        digest, scope = _dedup_hash(task.prefix, body)
        extra.update(sha256=digest, scope=scope)
        if digest == _latest_hash(task):
            storage.record(_KIND, task.url, "unchanged", ts=task.ts, sha256=digest, scope=scope)
            return "unchanged"

    path = storage.snapshot_path(task.hd, task.jcd, task.prefix, task.rno, task.ts)
    storage.write_gzip(path, body)
    storage.record(_KIND, task.url, "ok", **extra)
    return "ok"


def snapshot_once(
    fetcher: Fetcher,
    hd: str | None = None,
    prefixes: tuple[str, ...] = SNAPSHOT_PREFIXES,
    workers: int = 20,
) -> Counter[str]:
    """對某日目前開催中的所有場次拍一次快照。"""
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
