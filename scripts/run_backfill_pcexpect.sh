#!/bin/zsh
# pcexpect（コンピューター予想）最終版歷史回填（docs/decisions.md #7）：2017-04-01 起到昨天（JST）。
# 可中斷、可續跑：已存在的檔會 skip，不會重抓；插電後重跑同一個指令即可接續。
# 用 nohup + caffeinate -i 防閒置睡眠（合蓋仍會睡），log 在 logs/backfill_pcexpect.log。
# 看進度：tr '\r' '\n' < logs/backfill_pcexpect.log | grep -E '^20[0-9]{6}:' | tail -1
# 停止：pkill -f 'boatrace_crawler --workers .* race .*pcexpect'
cd "$(dirname "$0")/.."
mkdir -p logs

START="${START:-20170401}"
END="${END:-$(TZ=Asia/Tokyo date -v-1d +%Y%m%d)}"
WORKERS="${WORKERS:-200}"

echo "=== pcexpect backfill $START -> $END, workers=$WORKERS, $(date '+%F %T %Z') ===" >> logs/backfill_pcexpect.log
nohup caffeinate -i env PYTHONPATH=src .venv/bin/python -u -m boatrace_crawler --workers "$WORKERS" \
  race --start "$START" --end "$END" --prefixes pcexpect >> logs/backfill_pcexpect.log 2>&1 &
disown
echo "started pid=$! (log: logs/backfill_pcexpect.log)"
