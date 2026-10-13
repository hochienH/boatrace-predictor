#!/bin/zsh
# 歷史全量回填：2016-09-01 起，core 前綴（beforeinfo + odds3t）+ 每日 B/K LZH。
# 在 tmux 內執行，可安全斷線。
set -e
cd "$(dirname "$0")/.."
mkdir -p logs

START="${START:-20160901}"
END="${END:-$(TZ=Asia/Tokyo date +%Y%m%d)}"
WORKERS="${WORKERS:-200}"

echo "=== race (core) $START -> $END, workers=$WORKERS ==="
PYTHONPATH=src .venv/bin/python -u -m boatrace_crawler --workers "$WORKERS" \
  race --start "$START" --end "$END" --preset core

echo "=== lzh (B/K) $START -> $END ==="
PYTHONPATH=src .venv/bin/python -u -m boatrace_crawler --workers "$WORKERS" \
  lzh --start "$START" --end "$END"

echo "=== backfill done ==="
