"""平行執行小工具：固定 worker 數 + 進度輸出。"""

from __future__ import annotations

import sys
import threading
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")


def run_tasks(
    tasks: Iterable[T],
    worker: Callable[[T], str],
    workers: int,
    label: str,
) -> Counter[str]:
    """對每個 task 呼叫 worker，回傳 outcome 次數統計。worker 需自行處理例外語意。"""
    tasks = list(tasks)
    total = len(tasks)
    counts: Counter[str] = Counter()
    lock = threading.Lock()
    done = 0

    def wrapped(task: T) -> None:
        nonlocal done
        try:
            outcome = worker(task)
        except Exception as exc:  # 單一任務失敗不應中止整批
            outcome = f"error:{type(exc).__name__}"
        with lock:
            counts[outcome] += 1
            done += 1
            if done % 20 == 0 or done == total:
                sys.stderr.write(f"\r[{label}] {done}/{total} {dict(counts)}")
                sys.stderr.flush()

    if total:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(wrapped, tasks))
        sys.stderr.write("\n")
    return counts
