#!/bin/zsh
# 全量歷史回填：race(core preset) + B/K LZH，從 2016-09-01 到今天。
# racer / kibetsu 已在先前跑過，不與日期相關，這裡不重複執行。
set -e
cd "$(dirname "$0")/.."
mkdir -p logs
START="${START:-20160901}"
END="${END:-$(date +%Y%m%d)}"
WORKERS="${WORKERS:-50}"

echo "=== race (core preset) ${START} -> ${END} ==="
PYTHONPATH=src .venv/bin/python -u -m boatrace_crawler --workers "$WORKERS" \
  race --start "$START" --end "$END" --preset core

echo "=== lzh (B/K) ${START} -> ${END} ==="
PYTHONPATH=src .venv/bin/python -u -m boatrace_crawler --workers "$WORKERS" \
  lzh --start "$START" --end "$END"

echo "=== ALL DONE ==="
