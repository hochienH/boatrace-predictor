# 進度與交接（PROGRESS）

> 給下一個 session 的接手檔：先讀這裡，再讀 `docs/decisions.md`。REVIEW.md 是完整評估文件，不是進度檔。

## 目前狀態（2026-10-23）

- **原始資料**：`data/raw/race`（beforeinfo + odds3t，2016-09～2026-09 全量，13 GB）、`data/raw/lzh`（B/K/fan 檔）、`data/raw/racer`、`data/raw/odds_snapshot`（締切前快照，17 GB）。全部 gzip HTML／LZH，尚未 parse。
- **快照迴圈**：LaunchAgent `com.hochienh.boatrace-odds-snapshot`（plist 在 `scripts/launchd/`）直接執行 working tree 的 `scripts/run_odds_snapshot.sh`，每 180 秒一輪，`odds3t` 每輪落檔、`pcexpect` 內容變才落檔（`docs/decisions.md` #4、2026-10-23 備註）。
  - **改程式或切 branch 會立刻影響下一輪**，因為每輪都是新的 python process 讀 working tree。
  - 停止：`launchctl bootout gui/$(id -u)/com.hochienh.boatrace-odds-snapshot`；看狀態：`launchctl list | grep boatrace`；log 在 `logs/odds_snapshot.log`（進度列會洗版，看 `grep "^完成"`）。
  - Mac 睡眠時缺快照；PDT 深夜正是 JST 賽事時段。
- **分析層套件**：`.venv` 已裝 pandas 3.1 / pyarrow 26 / duckdb 2.0 / lxml / scipy / statsmodels / lightgbm 4.7；**lightgbm 還不能 import，缺 `brew install libomp`**（未裝，等使用者決定）。
- **測試**：`PYTHONPATH=src .venv/bin/python -m unittest tests.test_snapshot_dedup -v`。

## 快照資料的已知缺口（parser 要處理）

| 期間（JST） | odds3t | pcexpect |
|---|---|---|
| 2026-09-09～09-21 | 時區 bug：只有 JST 16 時後的場次有締切前軌跡，其餘是重複的締切後定格賠率 | 無 |
| 2026-09-22～10-12 | 完全缺（DNS 失敗後迴圈被 `set -e` 殺掉） | 無 |
| 2026-10-13～10-23 | 正常；但全天輪詢，締切後與深夜的檔是重複的最終賠率 | 無 |
| 2026-10-24 起 | 同上 | 開始累積當日變動軌跡；manifest 的 `unchanged` 列記錄沒落檔的那幾輪（`scope=region`） |

pcexpect 的**最終版**歷史頁（約 2017-04 起）仍抓得到、可用 race crawler 回填（決策 #7），快照只補「當日有沒有改過」。

parser 重建時系列時：丟掉時間戳晚於締切的檔；pcexpect 以檔案 ts 為「至少從此時起是這個內容」、以 manifest `unchanged` 的 ts 為「到此時仍相同」；`unchanged` 沒有 path，要靠目錄內 ts 順序 join，缺輪視為 unknown。`empty` 只代表尚未發布（JST 02 時前）、當日無開催或早於服務起點。

## 下一步（照 REVIEW §10 Phase 0 → 1）

1. B/K/fan 檔 parser → `data/parquet/<table>/year=YYYY/*.parquet`（決策 #3），先做 K 檔（結果＋締切賠率）與 B 檔（出走表）。
2. `odds3t` 歷史頁 parser → 120 組合-場表 + 市場隱含機率表（決策 #2 的主目標變數）。
3. 快照 parser（odds3t 時系列、pcexpect 版本序列）。
4. Phase 1 EDA：calibration curve、穴 base rate。

## 待使用者決定

- **pcexpect 歷史回填**（決策 #7）：`PYTHONPATH=src .venv/bin/python -m boatrace_crawler race --start 20170401 --end 20261023 --prefixes pcexpect`，約 55 萬請求、8～9 小時、7 GB；放 tmux／nohup 跑。先確認要不要跑、要從哪一年起。
- 快照請求量：目前 odds3t + pcexpect 各約 7 萬請求／天（24 小時不停、含已締切場次）。選項：維持；或只輪詢未締切的場次（讀頁面上的締切予定時刻）；或 pcexpect 降頻。
- `brew install libomp`（lightgbm 需要）。
- odds3t 要不要也套去重（可省約 2/3 磁碟；資訊不損失，因為 manifest 會記 unchanged）。

## 踩過的坑

- 本機時區是 PDT，「今天」一律用 `schedule.today_jst()`。
- 迴圈 shell 不能 `set -e` 殺整個 loop（已改）。
- 官方站 TTFB 固定 9～10 秒、與併發無關；併發 200 無限流。
- 探測頁面要先確認該場當天有開催：`schedule --date`。10-23 用沒開催的場地探 pcexpect，誤判成「歷史抓不到」，review 才抓出來。
- 整頁 hash 會被上方導覽表的 class 變動干擾，去重要切到本體區段（決策 #8）。
- 網頁每次回應只有一行 boomerang `<script>` 不同，去 script／style／註解後 sha256 才穩定。
