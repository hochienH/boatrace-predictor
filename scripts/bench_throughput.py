"""量測不同併發數下 boatrace.jp 的實際吞吐率（不落檔）。"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from boatrace_crawler.fetcher import Fetcher  # noqa: E402

URLS = [
    f"https://www.boatrace.jp/owpc/pc/race/odds3t?rno={rno}&jcd={jcd:02d}&hd=20260905"
    for jcd in (5, 6, 7, 8, 12, 13)
    for rno in range(1, 13)
]


def bench(workers: int, delay: float, n: int) -> None:
    fetcher = Fetcher(delay=delay, retries=1)
    urls = URLS[:n]
    t0 = time.perf_counter()
    latencies: list[float] = []

    def one(url: str) -> None:
        t = time.perf_counter()
        try:
            fetcher.get(url)
        except Exception as exc:
            print("  error", type(exc).__name__, exc)
        latencies.append(time.perf_counter() - t)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, urls))
    span = time.perf_counter() - t0
    latencies.sort()
    print(
        f"workers={workers:>3} delay={delay}  {n} req in {span:.1f}s "
        f"-> {n / span:.2f} req/s  p50={latencies[len(latencies) // 2]:.2f}s "
        f"max={latencies[-1]:.2f}s"
    )


if __name__ == "__main__":
    for workers in (1, 5, 10, 20):
        bench(workers, delay=0.0, n=min(len(URLS), max(10, workers * 2)))
