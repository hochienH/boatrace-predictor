"""締切前時系列快照：定時對當天開催中賽事的頁面存檔（不覆蓋，累積時間序列）。

官方歷史頁只保留締切那一刻的定格賠率（見 race.py 的歷史回補），這裡補的是締切前的變動軌跡——
歷史無法回補，只能從現在起持續累積（REVIEW.md §3.5、develop-plan-1.md）。
目前抓兩種頁（config.SNAPSHOT_PREFIXES）：odds3t（三連単賠率）與 pcexpect（コンピューター予想）。

兩個設計重點：
- 去重（docs/decisions.md #4／#8／#10）：兩種頁都「內容沒變就不寫檔」，沒變的那一輪仍寫一筆
  outcome=unchanged（含 ts、sha256）到 manifest，之後才能知道內容是在哪兩輪之間改的。
  「內容」只看本體（_DEDUP_REGIONS）：頁面上方的 レース／締切予定時刻 導覽表會隨當日進行移動
  is-activeColor1 之類的 class，整頁比對一天會誤判約 20 次。標記找不到（官方改版）就退回整頁比對，
  manifest 的 scope 欄位會變成 full，之後查得出來。
- 只輪詢發售中、未締切的場次（docs/decisions.md #9）：每場只在 JST SNAPSHOT_OPEN_JST 起、到該場
  締切予定時刻後 SNAPSHOT_GRACE_MINUTES 止之間輪詢。締切時刻從抓回頁面的導覽表解出、快取在
  storage.deadlines_path(hd)；每輪都重新解析、變了就更新，時刻調整也跟得上。還不知道時刻的場地
  （當日第一輪、解析失敗）照舊全部輪詢；--ignore-deadlines 可整輪關掉過濾。
設計成一次性函式，交給 scripts/run_odds_snapshot.sh 每隔固定秒數呼叫一次（cron 式輪詢）。
"""

from __future__ import annotations

import threading
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import schedule, storage
from .config import (
    JST,
    RACE_BASE,
    RACES_PER_DAY,
    SNAPSHOT_DEDUP_PREFIXES,
    SNAPSHOT_GRACE_MINUTES,
    SNAPSHOT_OPEN_JST,
    SNAPSHOT_PREFIXES,
)
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


# 去重時只比對這個區段：從「予選 1800m」標題區塊起到 </main> 為止。
# pcexpect：予想フォーカス／自信度／進入予想表與靜態注記；odds3t：オッズ更新時間＋三連単賠率表
# （發售前整段是「データはありません」）。都排除上方會隨時間變動的導覽表與頁首頁尾。
_DEDUP_REGIONS: dict[str, tuple[bytes, bytes]] = {
    "odds3t": (b'<div class="title16__add2020">', b"</main>"),
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


class DeadlineBook:
    """當日各場地的 締切予定時刻：先讀快取，輪詢中從抓回的頁面重新解析，變了就更新並在輪末存檔。"""

    def __init__(self, hd: str) -> None:
        self.hd = hd
        self.table: dict[str, schedule.Deadlines] = schedule.load_deadlines(hd)
        self._lock = threading.Lock()
        self._dirty = False

    def observe(self, jcd: str, body: bytes) -> None:
        parsed = schedule.parse_deadlines(body)
        if not parsed:
            return
        with self._lock:
            if self.table.get(jcd) != parsed:
                self.table[jcd] = parsed
                self._dirty = True

    def save(self) -> None:
        with self._lock:
            if self._dirty:
                schedule.save_deadlines(self.hd, self.table)
                self._dirty = False

    def active_races(self, jcd: str, now: datetime) -> list[int] | None:
        """現在該輪詢的 rno 清單；還不知道該場地的締切時刻就 None（呼叫端全部輪詢）。"""
        deadlines = self.table.get(jcd)
        if not deadlines or len(deadlines) < RACES_PER_DAY:
            return None
        if now < schedule.deadline_at(self.hd, SNAPSHOT_OPEN_JST):
            return []
        grace = timedelta(minutes=SNAPSHOT_GRACE_MINUTES)
        return [rno for rno, hhmm in sorted(deadlines.items()) if now <= schedule.deadline_at(self.hd, hhmm) + grace]


def _fetch_one(fetcher: Fetcher, task: SnapshotTask, book: DeadlineBook | None = None) -> str:
    try:
        body = fetcher.get(task.url)
    except FetchError:
        storage.record(_KIND, task.url, "failed", ts=task.ts)
        return "failed"
    if book is not None:
        book.observe(task.jcd, body)
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
    ignore_deadlines: bool = False,
    now: datetime | None = None,
) -> Counter[str]:
    """對某日目前發售中、未締切的所有場次拍一次快照。回傳的 Counter 另含 skipped（因時間窗沒發請求的頁數）。"""
    hd = hd or schedule.today_jst().strftime("%Y%m%d")
    venues = schedule.open_venues(fetcher, hd)
    if not venues:
        print(f"{hd}: 無開催，略過")
        return Counter()
    ts = int(time.time())
    now = now or datetime.now(JST)
    book = DeadlineBook(hd)
    counts: Counter[str] = Counter()
    tasks: list[SnapshotTask] = []
    for jcd in venues:
        rnos = None if ignore_deadlines else book.active_races(jcd, now)
        if rnos is None:
            rnos = list(range(1, RACES_PER_DAY + 1))
        counts["skipped"] += (RACES_PER_DAY - len(rnos)) * len(prefixes)
        tasks.extend(SnapshotTask(hd, jcd, rno, prefix, ts) for rno in rnos for prefix in prefixes)
    if tasks:
        counts += run_tasks(tasks, lambda t: _fetch_one(fetcher, t, book), workers=workers, label=f"snapshot:{hd}")
    book.save()
    return counts
