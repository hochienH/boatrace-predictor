"""官方 LZH 下載：番組表 (B)、競走成績 (K)、レーサー期別成績 (fan)。"""

from __future__ import annotations

import re
from collections import Counter

from . import storage
from .config import BASE, DOWNLOAD_PAGE, PROGRAM_BASE, RESULT_BASE
from .fetcher import Fetcher, FetchError
from .parallel import run_tasks
from .race import date_range

_FAN_RE = re.compile(r'href="(/static_extra/[^"]*/kibetsu/(fan\d{4}\.lzh))"')


def program_url(hd: str) -> str:
    return f"{PROGRAM_BASE}/{hd[:6]}/b{hd[2:]}.lzh"


def result_url(hd: str) -> str:
    return f"{RESULT_BASE}/{hd[:6]}/k{hd[2:]}.lzh"


def _fetch_lzh(fetcher: Fetcher, kind: str, url: str, filename: str, overwrite: bool) -> str:
    path = storage.lzh_path(kind, filename)
    if path.exists() and not overwrite:
        return "skip"
    try:
        body = fetcher.get(url)
    except FetchError:
        storage.record(f"lzh:{kind}", url, "failed")
        return "failed"
    storage.write_bytes(path, body)
    storage.record(f"lzh:{kind}", url, "ok", bytes=len(body))
    return "ok"


def crawl_daily_lzh(
    fetcher: Fetcher,
    start: str,
    end: str,
    workers: int = 5,
    overwrite: bool = False,
) -> Counter[str]:
    """B/K 檔以日期直接組 URL，不需經過網頁表單操作。"""
    jobs: list[tuple[str, str, str]] = []
    for hd in date_range(start, end):
        jobs.append(("b", program_url(hd), f"b{hd[2:]}.lzh"))
        jobs.append(("k", result_url(hd), f"k{hd[2:]}.lzh"))
    return run_tasks(
        jobs,
        lambda j: _fetch_lzh(fetcher, j[0], j[1], j[2], overwrite),
        workers=workers,
        label="lzh",
    )


def crawl_kibetsu(fetcher: Fetcher, workers: int = 5, overwrite: bool = False) -> Counter[str]:
    """期別成績檔是下載頁上的靜態連結，直接抽出來抓，不用猜檔名。"""
    html = fetcher.get_text(DOWNLOAD_PAGE)
    links = sorted(set(_FAN_RE.findall(html)))
    print(f"kibetsu: {len(links)} 個檔案")
    jobs = [("fan", BASE + href, name) for href, name in links]
    return run_tasks(
        jobs,
        lambda j: _fetch_lzh(fetcher, j[0], j[1], j[2], overwrite),
        workers=workers,
        label="kibetsu",
    )
