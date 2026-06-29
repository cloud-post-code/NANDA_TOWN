"""
scheduler.py
------------
Runs scrape_pricing.refresh_pricing_cache() once immediately at startup,
then again every day at midnight UTC.

Start with:
    python3 scheduler.py

Keep running in the background:
    nohup python3 scheduler.py >> scraper.log 2>&1 &

Or via the shell helper:
    ./run_daily.sh start
"""

import logging
import signal
import sys
import time
from datetime import datetime, timezone, timedelta
from threading import Event

from scrape_pricing import refresh_pricing_cache

log = logging.getLogger(__name__)

_stop_event = Event()


def _seconds_until_next_midnight_utc() -> float:
    now = datetime.now(timezone.utc)
    tomorrow_midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return (tomorrow_midnight - now).total_seconds()


def _run_once(label: str) -> None:
    log.info("=== Scrape starting: %s ===", label)
    try:
        result = refresh_pricing_cache()
        counts = {e["provider"]: e.get("count", 0) for e in result["scrape_log"]}
        log.info("=== Scrape done: %s — %d models total — %s ===",
                 label, len(result["all_models"]), counts)
    except Exception as exc:
        log.exception("=== Scrape FAILED: %s — %s ===", label, exc)


def run_loop() -> None:
    _run_once("startup")

    while not _stop_event.is_set():
        wait_secs = _seconds_until_next_midnight_utc()
        log.info("Next scrape in %.0f seconds (%.1f hours)", wait_secs, wait_secs / 3600)
        # Sleep in short slices so we can react to the stop signal promptly
        deadline = time.monotonic() + wait_secs
        while time.monotonic() < deadline and not _stop_event.is_set():
            _stop_event.wait(timeout=min(60, deadline - time.monotonic()))

        if _stop_event.is_set():
            break
        _run_once(f"daily {datetime.now(timezone.utc).date().isoformat()}")

    log.info("Scheduler stopped.")


def _handle_signal(sig, _frame):
    log.info("Signal %s received — stopping scheduler", sig)
    _stop_event.set()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
        stream=sys.stdout,
    )
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT,  _handle_signal)
    run_loop()
