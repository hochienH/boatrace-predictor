#!/bin/zsh
# 締切前賠率時系列快照：每隔 INTERVAL 秒對當天開催中賽事拍一次 odds3t，背景常駐執行。
set -e
cd "$(dirname "$0")/.."
mkdir -p logs

INTERVAL="${INTERVAL:-180}"

echo "=== odds snapshot loop, interval=${INTERVAL}s ==="
while true; do
  PYTHONPATH=src .venv/bin/python -u -m boatrace_crawler odds-snapshot
  sleep "$INTERVAL"
done
