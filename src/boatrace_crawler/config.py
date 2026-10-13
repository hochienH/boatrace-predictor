"""爬蟲設定：場地代碼、頁面前綴、路徑與預設參數。"""

from __future__ import annotations

from datetime import timedelta, timezone
from pathlib import Path

# 「今天」一律以 JST 判定（日本無夏令時間，固定 +9 即可）。
# 本機若在其他時區（例如 PDT 比 JST 慢 16 小時），用 date.today() 會在日本白天抓到前一天。
JST = timezone(timedelta(hours=9), "JST")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data"
RAW_ROOT = DATA_ROOT / "raw"
MANIFEST_PATH = RAW_ROOT / "_manifest.jsonl"

BASE = "https://www.boatrace.jp"
RACE_BASE = f"{BASE}/owpc/pc/race"
RACER_BASE = f"{BASE}/owpc/pc/data/racersearch"
DOWNLOAD_PAGE = f"{BASE}/owpc/pc/extra/data/download.html"
PROGRAM_BASE = "https://www1.mbrace.or.jp/od2/B"
RESULT_BASE = "https://www1.mbrace.or.jp/od2/K"

# jcd 是永久固定的場地代碼，不是每日流水號。
VENUES: dict[str, str] = {
    "01": "桐生",
    "02": "戸田",
    "03": "江戸川",
    "04": "平和島",
    "05": "多摩川",
    "06": "浜名湖",
    "07": "蒲郡",
    "08": "常滑",
    "09": "津",
    "10": "三国",
    "11": "びわこ",
    "12": "住之江",
    "13": "尼崎",
    "14": "鳴門",
    "15": "丸亀",
    "16": "児島",
    "17": "宮島",
    "18": "徳山",
    "19": "下関",
    "20": "若松",
    "21": "芦屋",
    "22": "福岡",
    "23": "唐津",
    "24": "大村",
}

RACE_PREFIXES: tuple[str, ...] = (
    "racelist",  # 出走表
    "beforeinfo",  # 直前情報
    "raceresult",  # 結果
    "odds3t",  # 三連単
    "odds3f",  # 三連複
    "odds2tf",  # 二連単・二連複
    "oddsk",  # 拡連複
    "oddstf",  # 単勝・複勝
    "pcexpect",  # コンピューター予想
)

# 第一階段全量回填只抓這兩個：直前情報與三連単賠率（REVIEW §3.4 / §3.5）。
# racelist / raceresult 的多數欄位可從 B / K 檔解出，賠率的其餘券種優先度低。
CORE_PREFIXES: tuple[str, ...] = ("beforeinfo", "odds3t")

RACER_PREFIXES: tuple[str, ...] = ("profile", "back3", "season", "course")

# 締切前賠率時系列快照只需要三連単（REVIEW §3.5 的 alpha 假說原料）。
SNAPSHOT_PREFIXES: tuple[str, ...] = ("odds3t",)
DEFAULT_SNAPSHOT_INTERVAL = 180  # 秒，run_odds_snapshot.sh 預設輪詢間隔

RACES_PER_DAY = 12
TOBAN_MIN = 1
TOBAN_MAX = 9999

# point-in-time DB（scripts/build_db.py 產生）。
DB_PATH = DATA_ROOT / "boatrace.db"

# 官方最早提供賽事頁的日期（develop-plan-1.md）。
EARLIEST_DATE = "20160901"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# 官方 TTFB 實測穩定在 9~10 秒，吞吐幾乎等於 workers / 10。
# 實測 200 併發下 18 req/s、0 錯誤；再高（400/600）雖然也沒被限流，
# 但考慮到這是公開實體博弈網站，不宜再往上拉。
DEFAULT_WORKERS = 200
DEFAULT_DELAY = 0.0  # 每個 worker 於請求之間的秒數；瓶頸是延遲不是頻次
DEFAULT_TIMEOUT = 60.0
DEFAULT_RETRIES = 3
COOLDOWN_BASE = 5.0  # 連續失敗時的全域降速秒數
COOLDOWN_MAX = 120.0
