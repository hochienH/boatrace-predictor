# 進度與交接（PROGRESS）

> 給下一個 session 的接手檔：先讀這裡，再讀 `docs/decisions.md`。REVIEW.md 是完整評估文件，不是進度檔。

## 目前狀態（2026-10-24 JST）

- **原始資料**：`data/raw/race`（beforeinfo + odds3t，2016-09～2026-09 全量，13 GB；pcexpect 回填中，見下）、`data/raw/lzh`（B/K/fan 檔）、`data/raw/racer`、`data/raw/odds_snapshot`（締切前快照，17 GB）。全部 gzip HTML／LZH，尚未 parse。
- **快照迴圈**：LaunchAgent `com.hochienh.boatrace-odds-snapshot`（plist 在 `scripts/launchd/`）直接執行 working tree 的 `scripts/run_odds_snapshot.sh`，每 180 秒一輪。**自 2026-10-24 08:44 JST 起**：只輪詢「JST 06:30 起、該場締切予定時刻 +20 分之前」的場次（決策 #9），`odds3t` 與 `pcexpect` 都內容變才落檔（#4／#8／#10）。締切時刻快取在 `data/raw/index/<year>/<hd>_deadlines.json`。
  - log 的 `完成：{...}` 行多了 `skipped`（因時間窗沒發的請求數）；`odds-snapshot --ignore-deadlines` 可整輪關掉過濾。
  - **改程式或切 branch 會立刻影響下一輪**，因為每輪都是新的 python process 讀 working tree；多檔修改要一次寫完（10-24 cli.py 先落地害一輪 TypeError）。
  - 停止：`launchctl bootout gui/$(id -u)/com.hochienh.boatrace-odds-snapshot`；看狀態：`launchctl list | grep boatrace`；log 在 `logs/odds_snapshot.log`（進度列會洗版，看 `grep "^完成"`）。
  - Pro 目前插電且 `pmset SleepDisabled 1`，合蓋不睡；若改回會睡，睡著那段就缺快照（PDT 深夜正是 JST 賽事時段）。使用者常從 Air ssh 進 Pro 開 session，長工作放 tmux。
- **pcexpect 歷史回填（決策 #7）— 跑中**：`scripts/run_backfill_pcexpect.sh`（2017-04-01 → 昨天，200 併發，在 Pro 的 tmux session `pcexpect` 前景跑＋`caffeinate -i`，log `logs/backfill_pcexpect.log`）。10-24 08:33 JST 啟動，08:55 誤以為要拔 Pro 的電源停過一次（到 2017-05-22），09:05 在 tmux 續跑。全程約 55 萬請求、實測約 6 天／分鐘 → 預計 10-24 19 時 JST 前後完成。中斷就重跑同一個腳本（已有檔 skip，跑過的日子幾秒帶過）。看進度：`tmux attach -t pcexpect`（Ctrl-b d 離開）或 `tr '\r' '\n' < logs/backfill_pcexpect.log | grep -E '^20[0-9]{6}:' | tail -1`。抽查 2017-04-02、04-20 的頁都有 予想フォーカス／自信度。完成後盤點：`find data/raw/race -name 'pcexpect_*' | wc -l` 應接近 2017-04 起 beforeinfo 的張數。
- **分析層套件**：`.venv` 已裝 pandas 3.1 / pyarrow 26 / duckdb 2.0 / lxml / scipy / statsmodels / lightgbm 4.7；`brew install libomp` 已裝（10-24），lightgbm 可 import。
- **測試**：`PYTHONPATH=src .venv/bin/python -m unittest tests.test_snapshot_dedup -v`（22 個）。

## 快照資料的已知缺口（parser 要處理）

| 期間（JST） | odds3t | pcexpect |
|---|---|---|
| 2026-09-09～09-21 | 時區 bug：只有 JST 16 時後的場次有締切前軌跡，其餘是重複的締切後定格賠率 | 無 |
| 2026-09-22～10-12 | 完全缺（DNS 失敗後迴圈被 `set -e` 殺掉） | 無 |
| 2026-10-13～10-24 08:40 | 全天輪詢、每輪落檔；發售前（約 06:47 前）本體是「データはありません」、締切後是重複的定格賠率 | 10-24 00:00 起才有：全天輪詢、內容變才落檔 |
| 2026-10-24 08:44 起 | 只輪詢 06:30～締切+20 分；內容變才落檔，沒變寫 manifest `unchanged`（`scope=region`） | 同左；02～06:30 之間的改版看不到 |

pcexpect 的**最終版**歷史頁（2017-04 起）由 race crawler 回填（上節），快照只補「當日有沒有改過」。

parser 重建時系列時（兩種頁同一套規則）：丟掉時間戳晚於締切的檔；檔案 ts 是「至少從此時起是這個內容」、manifest `unchanged` 的 ts 是「到此時仍相同」；`unchanged` 沒有 path，要靠目錄內 ts 順序 join，缺輪視為 unknown。manifest `empty` 只代表頁面沒有 `table1`（當日無開催、早於服務起點）；**「尚未發布」的頁有導覽表、記的是 `ok`**，本體是「※ データはありません。」（odds3t 發售前、pcexpect 02～04 時發布前都這樣），要看本體判斷。

## 下一步（照 REVIEW §10 Phase 0 → 1）

0. pcexpect 回填跑完後盤點張數（見上）；中斷就重跑 `scripts/run_backfill_pcexpect.sh`。
1. B/K/fan 檔 parser → `data/parquet/<table>/year=YYYY/*.parquet`（決策 #3），先做 K 檔（結果＋締切賠率）與 B 檔（出走表）。
2. `odds3t` 歷史頁 parser → 120 組合-場表 + 市場隱含機率表（決策 #2 的主目標變數）。
3. 快照 parser（odds3t 時系列、pcexpect 版本序列；規則見上節）。
4. Phase 1 EDA：calibration curve、穴 base rate。

## 待使用者決定

- 目前沒有。10-23 列的四項（pcexpect 回填、請求量、libomp、odds3t 去重）10-24 已照建議處理，見 `docs/decisions.md` #9／#10 與 2026-10-24 備註。

## 踩過的坑

- 本機時區是 PDT，「今天」一律用 `schedule.today_jst()`。
- 迴圈 shell 不能 `set -e` 殺整個 loop（已改）。
- 官方站 TTFB 固定 9～10 秒、與併發無關；併發 200 無限流。
- 探測頁面要先確認該場當天有開催：`schedule --date`。10-23 用沒開催的場地探 pcexpect，誤判成「歷史抓不到」，review 才抓出來。
- 整頁 hash 會被上方導覽表的 class 變動干擾，去重要切到本體區段（決策 #8）。
- 網頁每次回應只有一行 boomerang `<script>` 不同，去 script／style／註解後 sha256 才穩定。
- 發售從 JST 06:47 左右才開始、與該場 1R 締切時刻無關（夜場也是早上開賣）；之前的頁有導覽表但本體是「データはありません」，不會被判成 `empty`。
- working tree 是 live 的：多檔修改要一次落地，否則中間那一輪會跑到新舊不一致的程式。
