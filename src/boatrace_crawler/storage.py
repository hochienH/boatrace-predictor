"""原始檔落地：路徑配置、gzip 寫入、抓取紀錄。"""

from __future__ import annotations

import gzip
import json
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


def record(kind: str, url: str, outcome: str, **extra: object) -> None:
    """把每次抓取結果附加到 manifest，方便之後盤點缺漏。"""
    entry = {"ts": time.time(), "kind": kind, "url": url, "outcome": outcome, **extra}
    line = json.dumps(entry, ensure_ascii=False)
    with _manifest_lock:
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        with MANIFEST_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
