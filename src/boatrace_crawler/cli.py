"""命令列介面。"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import timedelta

from . import downloads, odds_snapshot, race, racer, schedule
from .config import (
    CORE_PREFIXES,
    DEFAULT_DELAY,
    DEFAULT_WORKERS,
    EARLIEST_DATE,
    RACE_PREFIXES,
    TOBAN_MAX,
    TOBAN_MIN,
)
from .fetcher import Fetcher

PRESETS: dict[str, tuple[str, ...]] = {"core": CORE_PREFIXES, "all": RACE_PREFIXES}


def _default_end() -> str:
    return schedule.today_jst().strftime("%Y%m%d")


def _default_start(days: int) -> str:
    return (schedule.today_jst() - timedelta(days=days - 1)).strftime("%Y%m%d")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="boatrace-crawler", description="boatrace.jp 原始資料爬蟲")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="每個 worker 請求間隔秒數")
    parser.add_argument("--overwrite", action="store_true", help="已存在的檔案也重抓")
    sub = parser.add_subparsers(dest="command", required=True)

    p_race = sub.add_parser("race", help="爬賽事頁面")
    p_race.add_argument("--start", default=None, help="YYYYMMDD，預設為 --days 推算")
    p_race.add_argument("--end", default=None, help="YYYYMMDD，預設今天")
    p_race.add_argument("--days", type=int, default=7, help="未給 --start 時往回抓的天數")
    p_race.add_argument("--preset", choices=sorted(PRESETS), default="core")
    p_race.add_argument(
        "--prefixes",
        nargs="+",
        choices=RACE_PREFIXES,
        default=None,
        help="指定時覆蓋 --preset",
    )

    p_lzh = sub.add_parser("lzh", help="爬官方 B/K 每日 LZH")
    p_lzh.add_argument("--start", default=None)
    p_lzh.add_argument("--end", default=None)
    p_lzh.add_argument("--days", type=int, default=7)

    sub.add_parser("kibetsu", help="爬レーサー期別成績 LZH（全期）")

    p_racer = sub.add_parser("racer", help="爬ボートレーサー検索頁面")
    p_racer.add_argument("--start", type=int, default=TOBAN_MIN)
    p_racer.add_argument("--end", type=int, default=TOBAN_MAX)

    p_sched = sub.add_parser("schedule", help="只列出某日開催場地")
    p_sched.add_argument("--date", required=True)

    p_snap = sub.add_parser("odds-snapshot", help="對當天開催中賽事拍一次賠率快照（給 cron/loop 輪詢用）")
    p_snap.add_argument("--date", default=None, help="YYYYMMDD，預設今天")

    p_all = sub.add_parser("all", help="依序跑完 race / lzh / kibetsu / racer")
    p_all.add_argument("--start", default=None)
    p_all.add_argument("--end", default=None)
    p_all.add_argument("--days", type=int, default=7)
    p_all.add_argument("--preset", choices=sorted(PRESETS), default="all")
    p_all.add_argument("--toban-start", type=int, default=TOBAN_MIN)
    p_all.add_argument("--toban-end", type=int, default=TOBAN_MAX)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    fetcher = Fetcher(delay=args.delay, pool_size=args.workers)
    counts: Counter[str] = Counter()

    if args.command == "schedule":
        venues = schedule.open_venues(fetcher, args.date)
        print(f"{args.date}: {' '.join(venues) if venues else '無開催'}")
        return 0

    if args.command == "odds-snapshot":
        counts = odds_snapshot.snapshot_once(fetcher, hd=args.date, workers=args.workers)
        print(f"完成：{dict(counts)}")
        return 0

    if args.command in ("race", "lzh", "all"):
        start = args.start or _default_start(args.days)
        end = args.end or _default_end()
        if start < EARLIEST_DATE:
            print(f"警告：{start} 早於官方最早提供的 {EARLIEST_DATE}")

    if args.command == "race":
        counts += race.crawl_dates(
            fetcher,
            race.date_range(start, end),
            prefixes=tuple(args.prefixes) if args.prefixes else PRESETS[args.preset],
            workers=args.workers,
            overwrite=args.overwrite,
        )
    elif args.command == "lzh":
        counts += downloads.crawl_daily_lzh(
            fetcher, start, end, workers=args.workers, overwrite=args.overwrite
        )
    elif args.command == "kibetsu":
        counts += downloads.crawl_kibetsu(fetcher, workers=args.workers, overwrite=args.overwrite)
    elif args.command == "racer":
        counts += racer.crawl_racers(
            fetcher, args.start, args.end, workers=args.workers, overwrite=args.overwrite
        )
    elif args.command == "all":
        counts += race.crawl_dates(
            fetcher,
            race.date_range(start, end),
            prefixes=PRESETS[args.preset],
            workers=args.workers,
            overwrite=args.overwrite,
        )
        counts += downloads.crawl_daily_lzh(
            fetcher, start, end, workers=args.workers, overwrite=args.overwrite
        )
        counts += downloads.crawl_kibetsu(fetcher, workers=args.workers, overwrite=args.overwrite)
        counts += racer.crawl_racers(
            fetcher,
            args.toban_start,
            args.toban_end,
            workers=args.workers,
            overwrite=args.overwrite,
        )
    else:  # pragma: no cover
        raise AssertionError(args.command)

    print(f"完成：{dict(counts)}")
    return 0
