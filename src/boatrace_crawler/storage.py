"""原始檔落地：路徑配置、gzip 寫入、抓取紀錄。"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import threading
import time
from pathlib import Path

from .config import MANIFEST_PATH, RAW_ROOT

_manifest_lock = threading.Lock()


def index_path(hd: str) -> Path:
    return RAW_ROOT / "index" / hd[:4] / f"{hd}.html.gz"


def race_path(hd: str, jcd: str, prefix: str, rno: int) -> Path:
    return RAW_ROOT / "race" / hd[:4] / hd / jcd / f"{prefix}_{rno:02d}.html.gz"


def racer_path(toban: int, prefix: str) -> Path:
    # 以千位分桶，避免單一目錄塞進上萬個子目錄。
    bucket = f"{toban // 1000:01d}xxx"
    return RAW_ROOT / "racer" / bucket / f"{toban:04d}" / f"{prefix}.html.gz"


def lzh_path(kind: str, filename: str) -> Path:
    return RAW_ROOT / "lzh" / kind / filename


def snapshot_path(hd: str, jcd: str, prefix: str, rno: int, ts: int) -> Path:
    # 每次快照獨立存檔（不覆蓋），用來重建締切前的賠率時系列。
    return RAW_ROOT / "odds_snapshot" / hd[:4] / hd / jcd / f"{prefix}_{rno:02d}" / f"{ts}.html.gz"


def deadlines_path(hd: str) -> Path:
    # 當日各場地 12 場的 締切予定時刻 快取（odds-snapshot 只輪詢未締切場次用），從賽事頁的導覽表解出。
    return RAW_ROOT / "index" / hd[:4] / f"{hd}_deadlines.json"


def latest_snapshot(hd: str, jcd: str, prefix: str, rno: int) -> Path | None:
    """同一場次目前最新的一張快照（依檔名時間戳），沒有就 None。寫到一半的 .tmp 不算。"""
    folder = snapshot_path(hd, jcd, prefix, rno, 0).parent
    if not folder.is_dir():
        return None
    candidates = [p for p in folder.glob("*.html.gz") if p.stem.removesuffix(".html").isdigit()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: int(p.stem.removesuffix(".html")))


_SCRIPT_RE = re.compile(rb"<script\b.*?</script>", re.S | re.I)
_STYLE_RE = re.compile(rb"<style\b.*?</style>", re.S | re.I)
_COMMENT_RE = re.compile(rb"<!--.*?-->", re.S)
_WS_RE = re.compile(rb"\s+")


def extract_region(body: bytes, start: bytes, end: bytes) -> tuple[bytes, bool]:
    """切出 start 標記（含）到其後第一個 end 標記（不含）之間的片段；任一標記找不到就回整份 body 與 False。"""
    i = body.find(start)
    if i < 0:
        return body, False
    j = body.find(end, i + len(start))
    if j < 0:
        return body, False
    return body[i:j], True


def content_hash(body: bytes) -> str:
    """去掉 <script>/<style>/HTML 註解並壓縮空白後的 sha256，用來判斷頁面「內容」有沒有變。

    官方頁每次回應只有一行 boomerang 監測 script 不同（docs/decisions.md 2026-10-22 備註），
    去掉之後同一份內容的 hash 才會穩定。
    """
    stripped = _SCRIPT_RE.sub(b"", body)
    stripped = _STYLE_RE.sub(b"", stripped)
    stripped = _COMMENT_RE.sub(b"", stripped)
    stripped = _WS_RE.sub(b" ", stripped).strip()
    return hashlib.sha256(stripped).hexdigest()


def write_gzip(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(tmp, "wb") as fh:
        fh.write(data)
    tmp.replace(path)


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def read_gzip(path: Path) -> bytes:
    with gzip.open(path, "rb") as fh:
        return fh.read()


def read_json(path: Path) -> object | None:
    """讀 JSON；檔案不存在或內容壞掉都回 None（呼叫端視同沒有快取）。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_json(path: Path, obj: object) -> None:
    write_bytes(path, json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1).encode("utf-8"))


def record(kind: str, url: str, outcome: str, **extra: object) -> None:
    """把每次抓取結果附加到 manifest，方便之後盤點缺漏。"""
    entry = {"ts": time.time(), "kind": kind, "url": url, "outcome": outcome, **extra}
    line = json.dumps(entry, ensure_ascii=False)
    with _manifest_lock:
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        with MANIFEST_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
