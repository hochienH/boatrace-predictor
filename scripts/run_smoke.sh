#!/bin/zsh
# 背景執行完整爬取流程，輸出寫入 logs/smoke.log
set -e
cd "$(dirname "$0")/.."
mkdir -p logs
PYTHONPATH=src nohup .venv/bin/python -u -m boatrace_crawler --workers "${WORKERS:-50}" \
  all --days "${DAYS:-7}" --preset "${PRESET:-all}" > logs/smoke.log 2>&1 &
echo "pid=$!"
