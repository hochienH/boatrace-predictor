#!/bin/zsh
# pcexpect（コンピューター予想）最終版歷史回填（docs/decisions.md #7）：2017-04-01 起到昨天（JST）。
# 可中斷、可續跑：已存在的檔會 skip，不會重抓；重跑同一個指令即可接續。
# 預設開一個 detached tmux session「pcexpect」在前景跑（SSH 斷線不受影響）：
#   看進度：tmux attach -t pcexpect（Ctrl-b d 離開）或 tr '\r' '\n' < logs/backfill_pcexpect.log | grep -E '^20[0-9]{6}:' | tail -1
#   停止：tmux kill-session -t pcexpect
# 沒有 tmux 就退回 nohup。兩種都用 caffeinate -i 防閒置睡眠（合蓋仍會睡）。
cd "$(dirname "$0")/.."
mkdir -p logs

START="${START:-20170401}"
END="${END:-$(TZ=Asia/Tokyo date -v-1d +%Y%m%d)}"
WORKERS="${WORKERS:-200}"
LOG=logs/backfill_pcexpect.log

if pgrep -f "boatrace_crawler --workers .* race .*--prefixes pcexpect" >/dev/null; then
  echo "已有一個 pcexpect 回填在跑（pgrep -fl boatrace_crawler），不重複啟動"; exit 1
fi

CMD="caffeinate -i env PYTHONPATH=src .venv/bin/python -u -m boatrace_crawler --workers $WORKERS race --start $START --end $END --prefixes pcexpect"
echo "=== pcexpect backfill $START -> $END, workers=$WORKERS, $(date '+%F %T %Z') ===" >> "$LOG"

if command -v tmux >/dev/null; then
  if tmux has-session -t pcexpect 2>/dev/null; then
    echo "tmux session 'pcexpect' 已存在：tmux attach -t pcexpect 看一下，確定沒在跑再 tmux kill-session -t pcexpect"; exit 1
  fi
  tmux new-session -d -s pcexpect -c "$PWD" "$CMD 2>&1 | tee -a $LOG; echo '=== 結束，按任意鍵關閉 ==='; read -k1"
  echo "started in tmux session 'pcexpect'（tmux attach -t pcexpect；log: $LOG）"
else
  nohup zsh -c "$CMD" >> "$LOG" 2>&1 &
  disown
  echo "started pid=$! with nohup（log: $LOG）"
fi
