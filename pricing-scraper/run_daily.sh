#!/usr/bin/env bash
# run_daily.sh — manage the pricing scraper background process
#
# Usage:
#   ./run_daily.sh start    # start scheduler in background
#   ./run_daily.sh stop     # send SIGTERM to stop it
#   ./run_daily.sh restart  # stop + start
#   ./run_daily.sh status   # show whether it's running
#   ./run_daily.sh once     # run a single scrape right now (foreground)
#   ./run_daily.sh cron     # print the crontab line to paste into `crontab -e`

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/scraper.pid"
LOG_FILE="$DIR/scraper.log"

_is_running() {
  [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

case "${1:-help}" in
  start)
    if _is_running; then
      echo "Already running (pid $(cat "$PID_FILE"))."
      exit 0
    fi
    cd "$DIR"
    nohup python3 scheduler.py >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Started (pid $!). Logs → $LOG_FILE"
    ;;

  stop)
    if ! _is_running; then
      echo "Not running."
      exit 0
    fi
    kill "$(cat "$PID_FILE")"
    rm -f "$PID_FILE"
    echo "Stopped."
    ;;

  restart)
    "$0" stop || true
    sleep 1
    "$0" start
    ;;

  status)
    if _is_running; then
      echo "Running (pid $(cat "$PID_FILE"))."
    else
      echo "Not running."
    fi
    ;;

  once)
    cd "$DIR"
    python3 scrape_pricing.py
    ;;

  cron)
    echo ""
    echo "Paste this into 'crontab -e' to run a fresh scrape at 00:05 every day:"
    echo ""
    echo "5 0 * * * cd $DIR && python3 scrape_pricing.py >> $LOG_FILE 2>&1"
    echo ""
    ;;

  *)
    echo "Usage: $0 {start|stop|restart|status|once|cron}"
    exit 1
    ;;
esac
