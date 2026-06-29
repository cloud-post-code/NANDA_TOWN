"""
Pricing Scraper Service
-----------------------
A standalone FastAPI service that:
 • Exposes /pricing/models endpoints (full catalog, filtered, single model)
 • Runs scrape_pricing.refresh_pricing_cache() once at startup
 • Re-runs the scrape every day at midnight UTC via a background thread

Start locally:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8001

The scraper writes pricing_cache.json next to this file.
The API reads from that file; if the file doesn't exist yet it falls back
to the hardcoded catalog inside scrape_pricing.py.
"""

import json
import logging
import signal
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from scrape_pricing import CACHE_PATH, refresh_pricing_cache

log = logging.getLogger(__name__)

# ── Daily scheduler (background thread) ───────────────────────────────────────

_stop_event = threading.Event()


def _seconds_until_next_midnight_utc() -> float:
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (tomorrow - now).total_seconds()


def _scrape_loop() -> None:
    while not _stop_event.is_set():
        wait = _seconds_until_next_midnight_utc()
        log.info("Next scrape in %.0fs (%.1fh)", wait, wait / 3600)
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline and not _stop_event.is_set():
            _stop_event.wait(timeout=min(60, deadline - time.monotonic()))
        if _stop_event.is_set():
            break
        label = f"daily {datetime.now(timezone.utc).date().isoformat()}"
        log.info("=== Daily scrape starting: %s ===", label)
        try:
            result = refresh_pricing_cache()
            log.info("=== Daily scrape done: %d models ===", len(result["all_models"]))
        except Exception as exc:
            log.exception("=== Daily scrape FAILED: %s ===", exc)
    log.info("Scrape loop stopped.")


# ── FastAPI lifespan ───────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup: run the first scrape, then launch the daily loop
    log.info("=== Startup scrape ===")
    try:
        result = refresh_pricing_cache()
        log.info("Startup scrape done: %d models", len(result["all_models"]))
    except Exception as exc:
        log.exception("Startup scrape failed: %s — will serve stale/fallback data", exc)

    t = threading.Thread(target=_scrape_loop, daemon=True, name="pricing-scraper")
    t.start()

    yield

    # Shutdown: stop the background thread
    _stop_event.set()
    t.join(timeout=5)


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="LLM Pricing Scraper",
    version="1.0.0",
    description=(
        "Daily-scraped token pricing for major LLM providers: "
        "Claude, GPT, Gemini, Llama (via Together AI), and GLM (Zhipu AI)."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ── Cache reader ───────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    """Read pricing_cache.json. Returns empty structure if file is missing."""
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text())
        except Exception as exc:
            log.warning("Could not read cache: %s", exc)
    return {"all_models": [], "scraped_at": None, "as_of": None}


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    cache = _load_cache()
    return {
        "service": "LLM Pricing Scraper",
        "version": "1.1.0",
        "docs": "/docs",
        "skill": "https://pricing-scraper-production.up.railway.app/skill.md",
        "scraped_at": cache.get("scraped_at"),
        "as_of": cache.get("as_of"),
        "model_count": len(cache.get("all_models", [])),
        "endpoints": {
            "all_models":     "GET /pricing/models",
            "filter":         "GET /pricing/models?provider=anthropic&family=claude",
            "single_model":   "GET /pricing/models/{model_id}",
            "scrape_status":  "GET /scrape/status",
            "trigger_scrape": "POST /scrape/run",
            "skill":          "GET /skill.md",
        },
    }


@app.get("/skill.md")
def serve_skill_md():
    from fastapi.responses import PlainTextResponse
    p = Path(__file__).parent / "SKILL.md"
    if p.exists():
        return PlainTextResponse(p.read_text())
    raise HTTPException(status_code=404, detail="SKILL.md not found")


@app.get("/pricing/models")
def get_model_pricing(
    provider: str | None = None,
    family: str | None = None,
):
    """Return token pricing for all major LLM models.

    Optional query params (case-insensitive substring match):
    - **provider**: e.g. `anthropic`, `openai`, `google`, `meta`, `zhipu`
    - **family**: e.g. `claude`, `gpt`, `gemini`, `llama`, `glm`
    """
    cache = _load_cache()
    all_models: list[dict] = cache.get("all_models", [])

    # Build grouped-by-family view
    by_family: dict[str, list] = {}
    for m in all_models:
        key = f"{m['provider']} / {m.get('family', '')}"
        by_family.setdefault(key, []).append(m)

    families = []
    for key, models in by_family.items():
        prov, fam = key.split(" / ", 1)
        families.append({"provider": prov, "family": fam, "models": models})

    base = {
        "scraped_at": cache.get("scraped_at"),
        "as_of": cache.get("as_of"),
        "currency": "USD",
        "note": cache.get("note", ""),
        "scrape_log": cache.get("scrape_log", []),
    }

    if provider or family:
        filtered = [
            m for m in all_models
            if (not provider or provider.lower() in m.get("provider", "").lower())
            and (not family or family.lower() in m.get("family", "").lower())
        ]
        return {
            **base,
            "filter": {"provider": provider, "family": family},
            "count": len(filtered),
            "models": filtered,
        }

    return {**base, "families": families, "all_models": all_models}


@app.get("/pricing/models/{model_id:path}")
def get_single_model_pricing(model_id: str):
    """Return pricing for one model by its exact model ID.

    Supports slash-separated IDs like `meta-llama/Llama-3.3-70B-Instruct-Turbo`.
    """
    cache = _load_cache()
    match = next(
        (m for m in cache.get("all_models", []) if m.get("model") == model_id),
        None,
    )
    if not match:
        available = [m["model"] for m in cache.get("all_models", [])]
        raise HTTPException(
            status_code=404,
            detail={"error": f"Model '{model_id}' not found.", "available": available},
        )
    return match


@app.get("/scrape/status")
def scrape_status():
    """Show when the last scrape ran and what it found."""
    cache = _load_cache()
    return {
        "scraped_at": cache.get("scraped_at"),
        "as_of": cache.get("as_of"),
        "model_count": len(cache.get("all_models", [])),
        "scrape_log": cache.get("scrape_log", []),
        "cache_path": str(CACHE_PATH),
        "cache_exists": CACHE_PATH.exists(),
    }


@app.post("/scrape/run", status_code=202)
def trigger_scrape():
    """Manually trigger a fresh scrape (runs synchronously, may take ~10s)."""
    try:
        result = refresh_pricing_cache()
        return {
            "status": "ok",
            "scraped_at": result["scraped_at"],
            "model_count": len(result["all_models"]),
            "scrape_log": result["scrape_log"],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
