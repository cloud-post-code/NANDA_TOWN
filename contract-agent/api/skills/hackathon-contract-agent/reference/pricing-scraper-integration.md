# Pricing Scraper Integration

## What the Pricing Scraper is

The LLM Pricing Scraper (`https://pricing-scraper-production.up.railway.app`) is a standalone service that scrapes provider pricing pages daily and exposes the results as a read-only JSON API.

It covers five provider families:

| Provider | Family | Example models |
|---|---|---|
| Anthropic | Claude | claude-opus-4-8, claude-sonnet-4-6, claude-haiku-4-5, claude-fable-5 |
| OpenAI | GPT | gpt-4o, gpt-4o-mini, o1, o3-mini |
| Google | Gemini | gemini-2.5-pro, gemini-2.5-flash, gemini-1.5-pro |
| Meta (via Together AI) | Llama | Llama-3.3-70B, Llama-3.1-405B, Llama-3.1-8B |
| Zhipu AI | GLM | glm-4-plus, glm-4, glm-4-flash |

Prices are in **USD per 1M tokens** and are refreshed every day at midnight UTC. The contract agent uses these live rates to populate the `rate_per_1k_usd` field in contract pricing tables.

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
          "model": "claude-opus-4-8",
          "display_name": "Claude Opus 4.8",
          "input_per_1m_usd": 5.00,
          "output_per_1m_usd": 25.00,
          "input_per_1k_usd": 0.005,
          "output_per_1k_usd": 0.025,
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
Filter by provider name or model family. Both params are optional and case-insensitive substring matches.

```bash
# All Claude models
curl "https://pricing-scraper-production.up.railway.app/pricing/models?provider=anthropic"

# All GPT models
curl "https://pricing-scraper-production.up.railway.app/pricing/models?family=gpt"

# Gemini models from Google
curl "https://pricing-scraper-production.up.railway.app/pricing/models?provider=google&family=gemini"
```

---

### GET /pricing/models/{model_id}
Return pricing for a single model by its exact ID. Supports slash-separated IDs.

```bash
# Claude
curl https://pricing-scraper-production.up.railway.app/pricing/models/claude-opus-4-8

# GPT
curl https://pricing-scraper-production.up.railway.app/pricing/models/gpt-4o

# Llama (slash in ID — URL-encode or pass directly)
curl "https://pricing-scraper-production.up.railway.app/pricing/models/meta-llama/Llama-3.3-70B-Instruct-Turbo"
```

**Response:**
```json
{
  "provider": "Anthropic",
  "family": "Claude",
  "model": "claude-opus-4-8",
  "display_name": "Claude Opus 4.8",
  "input_per_1m_usd": 5.00,
  "output_per_1m_usd": 25.00,
  "input_per_1k_usd": 0.005,
  "output_per_1k_usd": 0.025,
  "context_window_k": 1000,
  "notes": "Most capable Opus-tier model",
  "source": "https://www.anthropic.com/pricing"
}
```

---

### GET /scrape/status
Check when the last scrape ran and what it found. Useful for verifying data freshness before generating a contract.

```bash
curl https://pricing-scraper-production.up.railway.app/scrape/status
```

**Response:**
```json
{
  "scraped_at": "2026-06-29T00:05:01Z",
  "as_of": "2026-06-29",
  "model_count": 18,
  "scrape_log": [
    { "provider": "Anthropic",  "status": "ok", "count": 5 },
    { "provider": "OpenAI",     "status": "ok", "count": 6 },
    { "provider": "Google",     "status": "ok", "count": 4 },
    { "provider": "Together AI","status": "ok", "count": 3 },
    { "provider": "ZhipuAI",    "status": "ok", "count": 3 }
  ]
}
```

If a provider's scrape failed, its `status` will be `"error"` and cached data from the previous run is served instead.

---

## How the contract agent uses the Pricing Scraper

When setting `token_estimate` and computing contract USD costs, the agent should look up the live rate for the chosen model rather than relying on hardcoded rates.

**Recommended flow before calling `POST /contracts/generate`:**

1. Call `GET /pricing/models/{model_id}` to fetch the current `input_per_1k_usd` and `output_per_1k_usd` for the model that will run the service.
2. Use a blended rate (e.g. 60% input + 40% output) to estimate the per-token cost.
3. Multiply by your `token_estimate` to get the USD cost for the contract.
4. Pass the resolved `model` ID in the `POST /contracts/generate` body — the contract's Section 4 pricing table will reflect the live rate.

**Example — looking up Claude Opus 4.8 before generating:**
```bash
# 1. Get the live rate
rate=$(curl -s https://pricing-scraper-production.up.railway.app/pricing/models/claude-opus-4-8)
input_per_1k=$(echo $rate | jq '.input_per_1k_usd')
output_per_1k=$(echo $rate | jq '.output_per_1k_usd')

# 2. Compute blended rate (60% input, 40% output)
# blended_per_1k = input_per_1k * 0.6 + output_per_1k * 0.4

# 3. Generate the contract using that model
curl -X POST https://hackathon-contract-agent-production.up.railway.app/contracts/generate \
  -H "Content-Type: application/json" \
  -d '{ "model": "claude-opus-4-8", "token_estimate": 50000, ... }'
```

---

## Error handling

| HTTP status | Meaning | What to do |
|---|---|---|
| 200 | Prices returned | Use `scraped_at` to verify data is fresh (should be within 24 hours) |
| 404 | Model ID not found | Check the exact model ID against `GET /pricing/models`; model may have a different slug |
| 500 | Scraper internal error | Fall back to the hardcoded `MODEL_RATES` in the contract agent |
| Connection refused / timeout | Pricing scraper unavailable | Fall back to the hardcoded `MODEL_RATES`; log a warning in the contract |

If the Pricing Scraper is unreachable, the contract agent's built-in `MODEL_RATES` table is the fallback — contracts will still generate with hardcoded blended rates. The contract should note in the pricing section if live rates could not be fetched.

---

## Data freshness

- Scrape runs once daily at **midnight UTC**
- `scraped_at` in every response tells you exactly when the data was last refreshed
- Call `GET /scrape/status` to confirm the most recent scrape succeeded before generating a high-value contract
- If `scraped_at` is more than 48 hours ago, treat rates as potentially stale and note it in the contract
