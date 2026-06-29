# LLM Pricing Scraper

Provides daily-scraped token pricing for all major LLM providers. Returns `input_per_1k_usd` and `output_per_1k_usd` for any model. Use these rates to compute live USD costs in contracts or billing systems.

## Base URL

https://pricing-scraper-production.up.railway.app

## What it does

Scrapes public pricing pages from Anthropic, OpenAI, Google, Together AI (Llama), and ZhipuAI (GLM) once daily at midnight UTC. Exposes the results as a read-only JSON API. Caches the last successful scrape so stale data is served rather than empty data if a provider's page is temporarily unreachable.

**The scraper provides the per-token rate only.** Pricing math (price caps, upcharges, totals) is the caller's responsibility.

---

## Endpoints

### GET /pricing/models
Return all models from all providers, grouped by family.

```bash
curl https://pricing-scraper-production.up.railway.app/pricing/models
```

**Response:**
```json
{
  "scraped_at": "2026-06-29T00:05:01Z",
  "as_of": "2026-06-29",
  "currency": "USD",
  "families": [
    {
      "provider": "Anthropic",
      "family": "Claude",
      "models": [
        {
          "model": "claude-sonnet-4-6",
          "display_name": "Claude Sonnet 4.6",
          "input_per_1m_usd": 3.00,
          "output_per_1m_usd": 15.00,
          "input_per_1k_usd": 0.003,
          "output_per_1k_usd": 0.015,
          "context_window_k": 1000,
          "source": "https://www.anthropic.com/pricing"
        }
      ]
    }
  ],
  "all_models": [ ... ]
}
```

---

### GET /pricing/models?provider={provider}&family={family}
Filter by provider name or model family. Both params are optional, case-insensitive substring match.

```bash
# All Claude models
curl "https://pricing-scraper-production.up.railway.app/pricing/models?provider=anthropic"

# All GPT models
curl "https://pricing-scraper-production.up.railway.app/pricing/models?family=gpt"

# Gemini models only
curl "https://pricing-scraper-production.up.railway.app/pricing/models?provider=google&family=gemini"
```

**Response (filtered):**
```json
{
  "scraped_at": "2026-06-29T00:05:01Z",
  "as_of": "2026-06-29",
  "currency": "USD",
  "filter": { "provider": "anthropic", "family": null },
  "count": 5,
  "models": [ ... ]
}
```

---

### GET /pricing/models/{model_id}
Return pricing for one model by its exact model ID. Supports slash-separated IDs.

```bash
# Claude Sonnet
curl https://pricing-scraper-production.up.railway.app/pricing/models/claude-sonnet-4-6

# GPT-4o
curl https://pricing-scraper-production.up.railway.app/pricing/models/gpt-4o

# Llama (slash in ID)
curl "https://pricing-scraper-production.up.railway.app/pricing/models/meta-llama/Llama-3.3-70B-Instruct-Turbo"
```

**Response:**
```json
{
  "provider": "Anthropic",
  "family": "Claude",
  "model": "claude-sonnet-4-6",
  "display_name": "Claude Sonnet 4.6",
  "input_per_1m_usd": 3.00,
  "output_per_1m_usd": 15.00,
  "input_per_1k_usd": 0.003,
  "output_per_1k_usd": 0.015,
  "context_window_k": 1000,
  "notes": "Best speed/intelligence balance",
  "source": "https://www.anthropic.com/pricing"
}
```

**Error (model not found):**
```json
{ "detail": { "error": "Model 'bad-id' not found.", "available": [ ... ] } }
```

---

### GET /scrape/status
Check when the last scrape ran and what it found. Call this before generating a high-value contract to confirm data freshness.

```bash
curl https://pricing-scraper-production.up.railway.app/scrape/status
```

**Response:**
```json
{
  "scraped_at": "2026-06-29T00:05:01Z",
  "as_of": "2026-06-29",
  "model_count": 21,
  "scrape_log": [
    { "provider": "Anthropic",   "status": "ok",    "count": 5 },
    { "provider": "OpenAI",      "status": "ok",    "count": 6 },
    { "provider": "Google",      "status": "ok",    "count": 4 },
    { "provider": "Together AI", "status": "ok",    "count": 3 },
    { "provider": "ZhipuAI",     "status": "error", "error": "fetch failed" }
  ]
}
```

If a provider's `status` is `"error"`, its stale cached data is served. Check `scraped_at` — if it is >48 hours ago, treat rates as potentially stale and note this in any contract.

---

### POST /scrape/run
Manually trigger a fresh scrape (runs synchronously, ~10 seconds).

```bash
curl -X POST https://pricing-scraper-production.up.railway.app/scrape/run
```

---

## Provider coverage

| Provider | Family | Example models |
|---|---|---|
| Anthropic | Claude | claude-fable-5, claude-opus-4-8, claude-sonnet-4-6, claude-haiku-4-5 |
| OpenAI | GPT | gpt-4o, gpt-4o-mini, gpt-4-turbo, o1, o3-mini, o4-mini |
| Google | Gemini | gemini-2.5-pro, gemini-2.5-flash, gemini-1.5-pro, gemini-1.5-flash |
| Meta (via Together AI) | Llama | Llama-3.3-70B-Instruct-Turbo, Llama-3.1-405B, Llama-3.1-8B |
| Zhipu AI | GLM | glm-4-plus, glm-4, glm-4-flash |

---

## How an agent should use this

1. **Before generating a contract**, fetch the live rate for the model that will run the service:
   ```bash
   curl https://pricing-scraper-production.up.railway.app/pricing/models/claude-sonnet-4-6
   # → { "input_per_1k_usd": 0.003, "output_per_1k_usd": 0.015 }
   ```

2. **Compute a blended rate** for your workload (typical LLM workloads are ~60% input, 40% output):
   ```
   blended_per_1k = (input_per_1k_usd × 0.6) + (output_per_1k_usd × 0.4)
   ```
   For claude-sonnet-4-6: `(0.003 × 0.6) + (0.015 × 0.4) = 0.0078 USD/1k tokens`

3. **Pass the model ID** to `POST /contracts/generate` on the Contract Agent. The Contract Agent fetches the live rate automatically — you do not need to pass the rate separately.

4. **USD costs in the contract** are computed fresh on every `GET /contracts/{id}.md`. The token fields (price_cap, total_tokens) are static; only the dollar conversion uses the live rate.

---

## Fallback behavior

If a provider's pricing page cannot be scraped, the previously-cached data for that provider is preserved. The cache is never left completely empty. If the entire service is unreachable, the Contract Agent falls back to its built-in rate table and sets `rate_is_live: false` in the response.
