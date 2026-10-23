# 決策紀錄（Decision log）

> 格式：日期 / 決策 / 理由 / 影響。已決定的事不在對話中重新討論；要改就在這裡加一條新的，不改舊的。

## 2026-10-22　factor research 開跑前的六項決定

| # | 決策 | 理由 | 影響 |
|---|---|---|---|
| 1 | **時間切分**：development 2016-09～2021-12、validation 2022-01～2023-12、holdout 2024-01～2026-09。holdout 只在 Phase 4 go/no-go 看一次。2026-10-13 起的締切前賠率快照另作 forward test。 | 三年 holdout 才夠讓低命中率策略的 ROI 有統計意義（REVIEW §5.3）。2020 無観客留在 dev，EDA 時單獨檢查 regime change。 | 所有 factor 檢定與模型只能在 dev 上探索、在 validation 上複驗；任何人碰 holdout 前要先在本檔記一條。 |
| 2 | **factor 主目標變數**：對市場隱含機率的殘差。3連単締切賠率 → 去抽水、修正 favorite-longshot bias → 邊際化成各艇 1着／2着内／3着内機率；殘差＝實際−隱含。次指標：以締切最終賠率、扣 15% 折損的投注 ROI；第三：log-loss／Brier 相對市場的改善量。 | 市場已反映的 factor 不是 alpha（REVIEW §6.2 Benter 式思路）。 | 檢定框架先建「市場隱含機率」這張表，所有 factor 都對它比。 |
| 3 | **套件與儲存**：`.venv` 裝 pandas、pyarrow、duckdb、lxml、scipy、statsmodels、lightgbm；parse 結果存 Parquet，用 DuckDB 查；不用 polars、不用 PostgreSQL。 | 單機、資料量中等（約 15 萬場 × 6 艇 × 10 年），columnar + 內嵌查詢引擎最省事。 | parser 輸出 `data/parquet/<table>/year=YYYY/*.parquet`。lightgbm 在 macOS 需另裝 libomp（見 2026-10-22 備註）。 |
| 4 | **開始爬 pcexpect**（公式コンピューター予想）：加進締切前快照迴圈，與 odds3t 一樣每 180 秒輪詢，但「內容沒變就不寫檔」。 | 歷史抓不到、只能從現在累積；每日約 150～300 個請求，成本極低。develop-plan-1 的結論：進入予想可當 feature，自信度／予想フォーカス只拿來跟賠率比落差。 | 半年後才有可用樣本量。 |
| 5 | **Git 流程**：建立 `develop`，feature branch 完成後 merge 進 develop 並 push；`main` 不直接動。 | 使用者慣例。 | 2026-10-22 已建 develop 並 push。 |
| 6 | **競馬暫不進 scope**。factor 寫成 `(race_frame) -> Series` 的純函數、schema 不寫死六艇，之後競馬可重用；parser 與假說只做競艇。 | 先把一個市場做到有結論。 | — |

### 不另外討論、由執行者決定的細項
- 樣本單位兩張表都建：艇-場（每場 6 列）與 3連単 組合-場（每場 120 列）。
- 多重檢定：Benjamini–Hochberg q = 0.10，另設效果量門檻；單調性與分場／分年穩定性是必要條件。
- 「穴」只作 EDA 分桶（3連単 払戻 ≥ 5,000 円 與 ≥ 10,000 円 兩條線），不是目標變數。
- fan 檔（期別成績）當 point-in-time 選手特徵：某期開始時發布的「前期成績」在該期內可用；不用官方當期彙總。
- 選手頁（racersearch）是爬取當下快照，只用靜態欄位（生年月日、支部、出身、身長）。
- 快照間隔維持 180 秒。

### 2026-10-22 備註
- 快照去重的 hash：去掉 `<script>`／`<style>`／HTML 註解並壓縮空白後取 sha256。實測 10-21 締切後連續快照 hash 完全一致，逐次不同的只有一行 boomerang script。
- 2026-09-09～09-21 的快照有時區 bug（只有 JST 16 時後的場次有締切前軌跡），09-22～10-12 完全缺。詳見 git log 7b4abb6。

### 2026-10-23 備註（決策 #4 實作）
- `pcexpect` 已加進 `SNAPSHOT_PREFIXES`，去重只套用在 `SNAPSHOT_DEDUP_PREFIXES = ("pcexpect",)`；odds3t 維持每輪落檔。比對對象是同場次目錄裡時間戳最大的那張檔（沒有 sidecar 狀態檔，刪檔也不會失同步）；內容相同時仍寫一筆 `outcome=unchanged`（含 ts、sha256）到 manifest，之後可定位予想改在哪兩輪之間。
- 實測：JST 02 時隔天全部場次的 pcexpect 已發布。~~締切後約一天頁面變空殼~~ ← 這句是錯的，當時探測用的 `jcd=04` 在 10-21 沒開催，空殼是「該場當日無開催」不是「頁面過期」；更正見 #7。
- 請求量：決策寫「每日約 150～300 個請求」低估了——每 180 秒一輪、全天不停，實際 odds3t 一天約 7 萬個請求（10-21 落檔 70,044 張、726 MB），pcexpect 同頻率再加 7 萬。落檔量因去重只有百來張。要不要降頻／只輪詢未締切場次，待決。

## 2026-10-23　決策 #4 的前提更正與去重範圍

| # | 決策 | 理由 | 影響 |
|---|---|---|---|
| 7 | **pcexpect 歷史頁抓得到，#4 的「歷史抓不到、半年後才有樣本」不成立。** review workflow 對 2017-12～2026-10 的開催場次抽查，pcexpect 都回完整頁（3 個 `table1`、含自信度與予想フォーカス），且 2026-09-07 抓的 09-01 頁與今天重抓 hash 相同（頁面穩定）；2016-09～2017-03 的開催場次回「データはありません」或精簡版（無自信度），服務起點在 2017-03～2017-12 之間，未精確定位。快照迴圈的角色改為「當日予想有沒有被改過」，最終版用既有 race crawler（`pcexpect` 已在 `RACE_PREFIXES`）回填。 | 探測時用了當日沒開催的場地（見 10-23 備註）。 | **待使用者確認後**排一次 `race --prefixes pcexpect` 回填（2017-04～2026-10，約 55 萬請求、依 200 併發約 8～9 小時、約 7 GB gzip）；dev 2016-09～2017-03 這段沒有 pcexpect，factor 檢定要能容忍缺值。parser 把快照的 `empty` 定義為「尚未發布（JST 02 時前）／當日無開催／早於服務起點」，不是「頁面消失」。 |
| 8 | **pcexpect 去重只比對予想本體**：`<div class="title16__add2020">` 到 `</main>` 之間（予想フォーカス、自信度、進入予想表、靜態注記），去 script/style/註解再 hash；標記找不到就退回整頁，manifest `scope` 欄記 `region`／`full`。 | 頁面上方的「レース／締切予定時刻」導覽表會隨當日進行移動 `is-activeColor1`、`is-thColor2` 等 class，全站所有頁同步變；整頁比對實測一天誤判約 20 次／頁（10-23 odds3t 快照：締切後仍有 23 次整頁 hash 變動，區段 hash 只有 1 次）。 | 落檔量回到「真的改了才寫」。若官方改版讓標記消失，`scope=full` 會先出現在 manifest，再調標記即可。 |

## 2026-10-24　快照請求量、odds3t 去重與 #7 回填啟動

| # | 決策 | 理由 | 影響 |
|---|---|---|---|
| 9 | **快照只輪詢「發售中、未締切」的場次**：每場從 JST 06:30（`SNAPSHOT_OPEN_JST`）起輪詢，到該場締切予定時刻後 20 分鐘（`SNAPSHOT_GRACE_MINUTES`）止；間隔維持 180 秒。締切時刻從抓回頁面上方的導覽表解出（`schedule.parse_deadlines`），快取在 `data/raw/index/<year>/<hd>_deadlines.json`，每輪重新解析、變了就更新；還不知道時刻的場地（當日第一輪、解析失敗）全部輪詢；`odds-snapshot --ignore-deadlines` 可關掉。 | 10-23 實測（14 場地、75,768 張 odds3t 快照）：JST 06:30 前的 27% 請求本體全是「データはありません」——14 個場地都在 06:47～08:01 才首次出現賠率，與該場 1R 締切時刻無關（夜場也是早上開賣）；締切+20 分之後的 40% 是定格賠率。三個選項（維持／只輪詢未締切／pcexpect 降頻）中只有這個不損失資訊；pcexpect 降頻會失去「改在哪兩輪之間」的解析度。 | 請求量從每日約 14 萬降到約 5 萬（兩種頁合計）。代價：pcexpect 02～04 時發布後到 06:30 之間的改版看不到（最終版由 #7 回填補）；前日発売（SG 等）的前一天軌跡本來就沒抓。順延／時刻調整：還在輪詢中的場地會跟著更新，整個場地都過了窗口才改時刻就抓不到。10-24 08:44 JST 起生效。 |
| 10 | **odds3t 也套去重**，區段與 pcexpect 相同（`<div class="title16__add2020">` 到 `</main>`，含「オッズ更新時間」與三連単表），`SNAPSHOT_DEDUP_PREFIXES = ("odds3t", "pcexpect")`。 | 10-23 實測全日 odds3t 檔只有 8.9% 內容與前一張不同；即使只看 #9 的窗口內也只有 26%。manifest 的 `unchanged` 列（含 ts、sha256）保留「到此時仍相同」，資訊不損失。 | 每日 odds3t 落檔從約 7 萬張降到約 6～7 千張。parser 重建時系列時兩種頁同一套規則（檔案 ts＝至少從此時起、`unchanged` ts＝到此時仍相同）；10-24 08:44 JST 之前的 odds3t 是舊規則（每輪落檔）。 |

### 2026-10-24 備註
- **#7 回填已啟動**：`scripts/run_backfill_pcexpect.sh`（`race --start 20170401 --prefixes pcexpect`，200 併發，Pro 上 tmux session `pcexpect`＋`caffeinate -i`）。08:33 JST 起跑，08:55 誤判要拔 Pro 電源停過一次（到 2017-05-22、9,216 張），09:05 續跑；可中斷續跑，已有檔會 skip。抽查 2017-04-02、04-20 的頁都有 予想フォーカス 與 自信度，完整版服務起點早於 #7 估的區間下限。
- `brew install libomp` 已裝，lightgbm 4.7 可 import（決策 #3 的備註解除）。
- pcexpect 當日發布時間不固定：10-24 平和島 1R 在 02:06 與 03:59 的快照本體仍是「データはありません」，04:03 才有予想。這種頁含導覽表（有 `table1`），manifest 記 `ok` 不是 `empty`——「尚未發布」要看本體判斷，odds3t 發售前亦然。
- 部署 #9／#10 時 cli.py 比 odds_snapshot.py 早落地，08:40:53 JST 那一輪 TypeError 失敗、下一輪恢復；working tree 是 live 的，多檔修改要一次寫完。
