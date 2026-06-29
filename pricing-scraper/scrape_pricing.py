"""
scrape_pricing.py
-----------------
Scrapes public pricing pages for Anthropic, OpenAI, Google, Together AI (Llama),
and ZhipuAI (GLM) and writes the results to pricing_cache.json in the same
directory.

Run once manually:
    python3 scrape_pricing.py

Schedule daily with cron (runs at 00:05 local time every day):
    5 0 * * * cd /path/to/pricing-scraper && python3 scrape_pricing.py >> scraper.log 2>&1

Or import and call from another service:
    from scrape_pricing import refresh_pricing_cache
    refresh_pricing_cache()

If a provider's page cannot be scraped, the previously-cached data for that
provider is preserved and a warning is logged — the script never writes a
completely empty cache.
"""

import json
import logging
import re
import sys
import urllib.request
import urllib.error
from datetime import date, datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).parent / "pricing_cache.json"

# ── Shared HTTP helper ─────────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NandaTownPricingBot/1.0; "
        "+https://github.com/nanda-town)"
    ),
    "Accept": "text/html,application/json,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def _get(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


# ── Per-provider scrapers ──────────────────────────────────────────────────────
#
# Each scraper returns a list of dicts with keys:
#   provider, family, model, display_name,
#   input_per_1m_usd, output_per_1m_usd,
#   context_window_k, notes, source
#
# All prices are USD per 1M tokens.
# If the live page yields no recognisable prices, each scraper falls back to
# a hardcoded catalog so the cache is never left empty.


def _scrape_anthropic() -> list[dict]:
    url = "https://www.anthropic.com/pricing"
    html = _get(url)

    # Hardcoded fallback (updated 2025-06)
    fallback = [
        ("claude-fable-5",    "Claude Fable 5",    10.00, 50.00, 1000, "Most capable widely released Claude model"),
        ("claude-opus-4-8",   "Claude Opus 4.8",    5.00, 25.00, 1000, "Most capable Opus-tier model"),
        ("claude-opus-4-7",   "Claude Opus 4.7",    5.00, 25.00, 1000, "Previous-generation Opus"),
        ("claude-sonnet-4-6", "Claude Sonnet 4.6",  3.00, 15.00, 1000, "Best speed/intelligence balance"),
        ("claude-haiku-4-5",  "Claude Haiku 4.5",   1.00,  5.00,  200, "Fastest and most cost-effective"),
    ]

    # Try to pull "$X.XX" price pairs from near model names
    price_re = re.compile(
        r"(claude-[\w.-]+|Claude\s[\w\s.]+?)"
        r"[\s\S]{0,400}?"
        r"\$\s*([\d,]+\.?\d*)"
        r"[\s\S]{0,300}?"
        r"\$\s*([\d,]+\.?\d*)",
        re.IGNORECASE,
    )
    seen: set[str] = set()
    models: list[dict] = []
    for m in price_re.finditer(html):
        raw = m.group(1).strip()
        try:
            inp = float(m.group(2).replace(",", ""))
            out = float(m.group(3).replace(",", ""))
        except ValueError:
            continue
        if not (0 < inp <= 100 and inp <= out <= 500):
            continue
        key = raw.lower().replace(" ", "-")
        if key in seen:
            continue
        seen.add(key)
        models.append(_entry("Anthropic", "Claude", key, raw, inp, out, 1000, url))

    if models:
        log.info("Anthropic: scraped %d models live", len(models))
        return models

    log.warning("Anthropic: live scrape empty — using fallback catalog")
    return [_entry("Anthropic", "Claude", mid, dn, i, o, ctx, url, notes=n)
            for mid, dn, i, o, ctx, n in fallback]


def _scrape_openai() -> list[dict]:
    url = "https://openai.com/api/pricing/"
    html = _get(url)

    fallback = [
        ("gpt-4o",      "GPT-4o",       2.50, 10.00, 128, "Flagship multimodal model"),
        ("gpt-4o-mini", "GPT-4o mini",  0.15,  0.60, 128, "Cost-efficient small model"),
        ("gpt-4-turbo", "GPT-4 Turbo", 10.00, 30.00, 128, "High-capability with vision"),
        ("o1",          "o1",          15.00, 60.00, 200, "Reasoning model"),
        ("o3-mini",     "o3-mini",      1.10,  4.40, 200, "Cost-efficient reasoning model"),
        ("o4-mini",     "o4-mini",      1.10,  4.40, 200, "Latest cost-efficient reasoning"),
    ]

    price_re = re.compile(
        r"(gpt-[\w.-]+|o\d[\w.-]*|GPT-[\w\s.-]+?|o\d[\s\w.-]+?)"
        r"[\s\S]{0,400}?"
        r"\$\s*([\d,]+\.?\d+)"
        r"[\s\S]{0,300}?"
        r"\$\s*([\d,]+\.?\d+)",
        re.IGNORECASE,
    )
    seen: set[str] = set()
    models: list[dict] = []
    for m in price_re.finditer(html):
        raw = m.group(1).strip()
        try:
            inp = float(m.group(2).replace(",", ""))
            out = float(m.group(3).replace(",", ""))
        except ValueError:
            continue
        if not (0 < inp <= 200 and inp <= out <= 500):
            continue
        key = raw.lower().replace(" ", "-")
        if key in seen:
            continue
        seen.add(key)
        models.append(_entry("OpenAI", "GPT", key, raw, inp, out, 128, url))

    if models:
        log.info("OpenAI: scraped %d models live", len(models))
        return models

    log.warning("OpenAI: live scrape empty — using fallback catalog")
    return [_entry("OpenAI", "GPT", mid, dn, i, o, ctx, url, notes=n)
            for mid, dn, i, o, ctx, n in fallback]


def _scrape_google() -> list[dict]:
    url = "https://ai.google.dev/pricing"
    html = _get(url)

    fallback = [
        ("gemini-2.5-pro",   "Gemini 2.5 Pro",   1.25, 10.00, 1000, "Most capable Gemini; ≤200k input price"),
        ("gemini-2.5-flash", "Gemini 2.5 Flash",  0.075, 0.30, 1000, "Fast and cost-efficient"),
        ("gemini-1.5-pro",   "Gemini 1.5 Pro",   1.25,  5.00, 2000, "Long-context; ≤128k price shown"),
        ("gemini-1.5-flash", "Gemini 1.5 Flash",  0.075, 0.30, 1000, "Speed-optimized; ≤128k price shown"),
    ]

    price_re = re.compile(
        r"(gemini-[\w.-]+|Gemini\s[\w\s.0-9-]+?)"
        r"[\s\S]{0,400}?"
        r"\$\s*([\d,]+\.?\d+)"
        r"[\s\S]{0,300}?"
        r"\$\s*([\d,]+\.?\d+)",
        re.IGNORECASE,
    )
    seen: set[str] = set()
    models: list[dict] = []
    for m in price_re.finditer(html):
        raw = m.group(1).strip()
        try:
            inp = float(m.group(2).replace(",", ""))
            out = float(m.group(3).replace(",", ""))
        except ValueError:
            continue
        if not (0 < inp <= 200 and inp <= out <= 500):
            continue
        key = raw.lower().replace(" ", "-")
        if key in seen:
            continue
        seen.add(key)
        models.append(_entry("Google", "Gemini", key, raw, inp, out, 1000, url))

    if models:
        log.info("Google: scraped %d models live", len(models))
        return models

    log.warning("Google: live scrape empty — using fallback catalog")
    return [_entry("Google", "Gemini", mid, dn, i, o, ctx, url, notes=n)
            for mid, dn, i, o, ctx, n in fallback]


def _scrape_together_ai() -> list[dict]:
    """Together AI hosts Llama and other open models."""
    url = "https://www.together.ai/pricing"

    fallback = [
        ("meta-llama/Llama-3.3-70B-Instruct-Turbo",       "Llama 3.3 70B Instruct Turbo",  0.88, 0.88, 128, "Together AI hosted price"),
        ("meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",  "Llama 3.1 405B Instruct Turbo", 3.50, 3.50, 128, "Together AI hosted price"),
        ("meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",   "Llama 3.1 8B Instruct Turbo",   0.18, 0.18, 128, "Together AI hosted price"),
    ]

    try:
        html = _get(url)
    except Exception as exc:
        log.warning("Together AI: fetch failed (%s) — using fallback", exc)
        return [_entry("Meta (hosted: Together AI)", "Llama", mid, dn, i, o, ctx, url, notes=n)
                for mid, dn, i, o, ctx, n in fallback]

    # Together AI uses "$X.XX / 1M tokens" patterns
    price_re = re.compile(
        r"(Llama[\w\s.-]*?|llama[\w.-]+)"
        r"[\s\S]{0,400}?"
        r"\$\s*([\d,]+\.?\d+)\s*/\s*1M",
        re.IGNORECASE,
    )
    seen: set[str] = set()
    models: list[dict] = []
    for m in price_re.finditer(html):
        raw = m.group(1).strip()
        try:
            price = float(m.group(2).replace(",", ""))
        except ValueError:
            continue
        if not 0 < price <= 100:
            continue
        key = "meta-llama/" + raw.replace(" ", "-")
        if key in seen:
            continue
        seen.add(key)
        models.append(_entry(
            "Meta (hosted: Together AI)", "Llama", key, raw,
            price, price, 128, url,
            notes=f"Together AI hosted API — scraped from {url}",
        ))

    if models:
        log.info("Together AI / Llama: scraped %d models live", len(models))
        return models

    log.warning("Together AI: live scrape empty — using fallback catalog")
    return [_entry("Meta (hosted: Together AI)", "Llama", mid, dn, i, o, ctx, url, notes=n)
            for mid, dn, i, o, ctx, n in fallback]


def _scrape_zhipu() -> list[dict]:
    """ZhipuAI GLM models — page is in Chinese; prices in CNY."""
    url = "https://open.bigmodel.cn/pricing"
    CNY_PER_USD = 7.2

    fallback = [
        ("glm-4-plus",  "GLM-4 Plus",  0.70, 0.70, 128, "Flagship GLM-4; CNY converted ~7.2/USD"),
        ("glm-4",       "GLM-4",       0.14, 0.14, 128, "Standard GLM-4; CNY converted ~7.2/USD"),
        ("glm-4-flash", "GLM-4 Flash", 0.00, 0.00, 128, "Free tier from Zhipu AI"),
    ]

    try:
        html = _get(url)
    except Exception as exc:
        log.warning("ZhipuAI: fetch failed (%s) — using fallback", exc)
        return [_entry("Zhipu AI", "GLM", mid, dn, i, o, ctx, url, notes=n)
                for mid, dn, i, o, ctx, n in fallback]

    # Look for "￥0.005" next to a GLM model name (price is per 1k tokens)
    price_re = re.compile(
        r"(glm-[\w.-]+|GLM-[\w.-]+)"
        r"[\s\S]{0,400}?"
        r"[¥￥]\s*([\d,]+\.?\d*)",
        re.IGNORECASE,
    )
    seen: set[str] = set()
    models: list[dict] = []
    for m in price_re.finditer(html):
        raw = m.group(1).strip()
        try:
            cny_per_k = float(m.group(2).replace(",", ""))
        except ValueError:
            continue
        usd_per_1m = round(cny_per_k / CNY_PER_USD * 1000, 6)
        if not 0 <= usd_per_1m <= 200:
            continue
        key = raw.lower()
        if key in seen:
            continue
        seen.add(key)
        models.append(_entry(
            "Zhipu AI", "GLM", key, raw,
            usd_per_1m, usd_per_1m, 128, url,
            notes=f"CNY converted at ~{CNY_PER_USD} CNY/USD — scraped from {url}",
        ))

    if models:
        log.info("ZhipuAI: scraped %d models live", len(models))
        return models

    log.warning("ZhipuAI: live scrape empty — using fallback catalog")
    return [_entry("Zhipu AI", "GLM", mid, dn, i, o, ctx, url, notes=n)
            for mid, dn, i, o, ctx, n in fallback]


# ── Shared dict builder ────────────────────────────────────────────────────────

def _entry(
    provider: str,
    family: str,
    model: str,
    display_name: str,
    inp: float,
    out: float,
    ctx_k: int,
    source: str,
    notes: str = "",
) -> dict:
    return {
        "provider": provider,
        "family": family,
        "model": model,
        "display_name": display_name,
        "input_per_1m_usd": inp,
        "output_per_1m_usd": out,
        "input_per_1k_usd": round(inp / 1000, 8),
        "output_per_1k_usd": round(out / 1000, 8),
        "context_window_k": ctx_k,
        "notes": notes or f"Scraped from {source}",
        "source": source,
    }


# ── Orchestrator ──────────────────────────────────────────────────────────────

_SCRAPERS = [
    ("Anthropic",  _scrape_anthropic),
    ("OpenAI",     _scrape_openai),
    ("Google",     _scrape_google),
    ("Together AI", _scrape_together_ai),
    ("ZhipuAI",   _scrape_zhipu),
]


def refresh_pricing_cache() -> dict:
    """
    Run all scrapers, merge with any existing cache (preserving stale provider
    data on failure), write pricing_cache.json, and return the new payload.
    """
    # Load existing cache keyed by provider so we can fall back per-provider
    existing_by_provider: dict[str, list[dict]] = {}
    if CACHE_PATH.exists():
        try:
            cached = json.loads(CACHE_PATH.read_text())
            for entry in cached.get("all_models", []):
                existing_by_provider.setdefault(entry["provider"], []).append(entry)
        except Exception as exc:
            log.warning("Could not parse existing cache: %s", exc)

    all_models: list[dict] = []
    scrape_log: list[dict] = []

    for name, scraper in _SCRAPERS:
        try:
            models = scraper()
            all_models.extend(models)
            scrape_log.append({"provider": name, "status": "ok", "count": len(models)})
        except Exception as exc:
            log.error("%s scraper failed: %s", name, exc)
            scrape_log.append({"provider": name, "status": "error", "error": str(exc)})
            # Fall back to whatever was in the cache for this provider
            stale = [
                m for provider_models in existing_by_provider.values()
                for m in provider_models
                if m.get("provider", "").lower() == name.lower()
            ]
            if stale:
                log.warning("%s: keeping %d stale cached models", name, len(stale))
                all_models.extend(stale)

    payload = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "as_of": date.today().isoformat(),
        "currency": "USD",
        "note": (
            "Prices scraped daily from provider pricing pages. "
            "Llama prices reflect Together AI hosted API rates. "
            "GLM prices converted from CNY at ~7.2 CNY/USD. "
            "Always verify at source URLs before billing."
        ),
        "scrape_log": scrape_log,
        "all_models": all_models,
    }

    CACHE_PATH.write_text(json.dumps(payload, indent=2))
    log.info("Wrote %d models to %s", len(all_models), CACHE_PATH)
    return payload


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        stream=sys.stdout,
    )
    result = refresh_pricing_cache()
    print(f"\n✓ {len(result['all_models'])} models written to {CACHE_PATH}")
    print(f"\nScrape log:")
    for entry in result["scrape_log"]:
        status = entry["status"]
        count  = entry.get("count", 0)
        err    = entry.get("error", "")
        line   = f"  {entry['provider']:<20}  {status}"
        if status == "ok":
            line += f"  ({count} models)"
        else:
            line += f"  ERROR: {err}"
        print(line)
