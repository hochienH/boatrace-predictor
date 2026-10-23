#!/bin/zsh
# 締切前時系列快照：每隔 INTERVAL 秒對當天「發售中、未締切」的場次拍一次 odds3t 與 pcexpect（內容沒變不落檔），背景常駐執行。
set -e
cd "$(dirname "$0")/.."
mkdir -p logs

INTERVAL="${INTERVAL:-180}"

echo "=== odds snapshot loop, interval=${INTERVAL}s ==="
while true; do
  # 單輪失敗（斷網、DNS 解析失敗等）只記錄、下一輪重試；不可讓 set -e 結束整個迴圈
  # （2026-09-22 曾因一次 DNS 失敗整個停擺三週，快照歷史無法回補）。
  if ! PYTHONPATH=src .venv/bin/python -u -m boatrace_crawler odds-snapshot; then
    echo "[$(TZ=Asia/Tokyo date '+%F %T JST')] 本輪快照失敗，${INTERVAL}s 後重試"
  fi
  sleep "$INTERVAL"
done
