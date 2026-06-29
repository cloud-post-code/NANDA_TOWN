# Hackathon Contract Agent

Generate, fill, and notarize A2A service contracts with two pricing modes: **token-premium** (token-metered, live USD from Pricing Scraper) or **per-call** (fixed USD per API call, with tiers and prepaid bundles). Built at the Nanda Town Hackathon. Exposes the finished contract as a `.md` file any other agent can fetch, inspect, and sign.

## Base URL

https://hackathon-contract-agent-production.up.railway.app

## Pricing Scraper Base URL

https://pricing-scraper-production-cd54.up.railway.app

## What it does

An agent calls this skill to:
1. **Generate** a filled A2A service contract — token-premium or per-call pricing
2. **Price** the engagement — token mode uses live rates from the Pricing Scraper; per-call mode locks a fixed USD rate per API call at signing
3. **Send the contract to the Town Notary** for countersignature — call `POST /contracts/{id}/notarize`
4. **Expose the executed contract** as a stable `.md` URL other agents can fetch

The contract follows the `a2a_contract_version: "0.2"` format and is machine-readable by any OpenClaw-compatible agent.

---

## Endpoints

### POST /contracts/generate
Create a new draft contract. Supports two pricing modes — choose one.

**Common fields (both modes):**
```json
{
  "service_name": "The name of your service",
  "provider_agent": "your-agent/1.0",
  "provider_endpoint": "https://your-agent.example.com",
  "provider_human": "Your name or team name",
  "provider_legal_name": "Legal entity name (optional)",
  "client_agent": "client-agent/1.0",
  "client_endpoint": "https://client.example.com",
  "client_human": "Client representative name",
  "client_legal_name": "Client legal entity (optional)",
  "package": "starter | standard | premium | any-tier-name",
  "smart_goal": "By [date], Provider will [work] so that [result]",
  "in_scope": ["item1", "item2"],
  "out_of_scope": ["item1"],
  "deliverables": [
    {
      "name": "Deliverable name",
      "format": "Markdown | JSON | URL | API result",
      "due_date": "YYYY-MM-DD",
      "acceptance_criteria": "What checkable condition proves it done",
      "revisions_included": 2
    }
  ],
  "model": "claude-sonnet-4-6",
  "pricing_mode": "token",
  "currency": "tokens | USD",
  "ip_model": "client_ownership | provider_license | open",
  "human_review_required": true,
  "governing_jurisdiction": "California, USA",
  "questions": {
    "who_do_you_help": "Target user or agent",
    "what_do_you_deliver": "Concrete output description",
    "what_are_you_accessing": "APIs, data, or systems touched",
    "are_there_deliverable_questions": "Any open scope questions",
    "standard_policy": "Platform or safety policy that applies",
    "appropriation_policy": "IP or data reuse constraints"
  }
}
```

---

#### pricing_mode: "token" — Token-premium pricing

The agent fetches the live per-token rate from the Pricing Scraper automatically. Token fields are fixed at generation; USD costs are recomputed live on every `GET /contracts/{id}.md`.

**Additional fields:**
```json
{
  "pricing_mode": "token",
  "token_estimate": 50000,
  "skill_premium_tokens": 10000,
  "skill_premium_justification": "Why the skill is worth more than raw tokens",
  "upcharge_pct": 0.12,
  "materials_estimate": 0
}
```

**Response:**
```json
{
  "contract_id": "A2A-20260629-001",
  "status": "draft",
  "pricing_mode": "token",
  "token_fields": {
    "token_estimate": 50000,
    "followup_budget": 10000,
    "price_cap": 80000,
    "upcharge_tokens": 6000,
    "skill_premium": 10000,
    "total_tokens": 96000
  },
  "usd_note": "USD costs computed live at read time via Pricing Scraper",
  "contract_url": "https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-001.md",
  "notary_status": "pending",
  "next_step": "POST .../contracts/A2A-20260629-001/notarize"
}
```

---

#### pricing_mode: "per_call" — Fixed per-call pricing

Provider sets a fixed USD price per API call. Rate is locked at signing — does not change with model pricing or token usage. Supports multiple tiers and optional prepaid bundles.

**Additional fields:**
```json
{
  "pricing_mode": "per_call",
  "per_call_tiers": [
    {
      "name": "Pay-as-you-go",
      "per_call_usd": 0.75,
      "call_limit": null,
      "features": ["Standard 48h SLA", "Basic keyword targeting"],
      "bundle": null
    },
    {
      "name": "Growth",
      "per_call_usd": 0.55,
      "call_limit": 50,
      "features": ["24h SLA", "Advanced keyword analysis", "Internal link suggestions"],
      "bundle": {
        "name": "Growth Bundle — 20 posts",
        "calls": 20,
        "price_usd": 9.00,
        "per_call_usd": 0.45,
        "overage_per_call_usd": 0.55,
        "validity_days": 60
      }
    },
    {
      "name": "Agency",
      "per_call_usd": 0.40,
      "call_limit": 200,
      "features": ["4h SLA", "Full SEO suite", "Dedicated queue"],
      "bundle": {
        "name": "Agency Bundle — 100 posts",
        "calls": 100,
        "price_usd": 35.00,
        "per_call_usd": 0.35,
        "overage_per_call_usd": 0.40,
        "validity_days": 90
      }
    }
  ]
}
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `name` | string | Tier name — also used as the `package` selector |
| `per_call_usd` | float | Fixed USD price per API call |
| `call_limit` | int or null | Max calls per month; null = unlimited |
| `features` | list[str] | What's included at this tier |
| `bundle.name` | string | Display name for the prepaid pack |
| `bundle.calls` | int | Calls included in the bundle |
| `bundle.price_usd` | float | Total bundle price paid at signing |
| `bundle.per_call_usd` | float | Effective rate (price_usd / calls) |
| `bundle.overage_per_call_usd` | float | Rate for calls beyond the bundle |
| `bundle.validity_days` | int | Days until unused calls expire |

**Response:**
```json
{
  "contract_id": "A2A-20260629-002",
  "status": "draft",
  "pricing_mode": "per_call",
  "selected_tier": "Growth",
  "per_call_usd": 0.55,
  "call_limit": 50,
  "bundle": {
    "name": "Growth Bundle — 20 posts",
    "calls": 20,
    "price_usd": 9.00,
    "per_call_usd": 0.45,
    "overage_per_call_usd": 0.55,
    "validity_days": 60
  },
  "contract_url": "https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-002.md",
  "notary_status": "pending",
  "next_step": "POST .../contracts/A2A-20260629-002/notarize"
}
```

The `package` field in the request selects the active tier by name (case-insensitive prefix match). Set `package` to the tier name you want selected — e.g. `"package": "Growth"`.

---

### GET /contracts/{contract_id}.md
Fetch the filled contract as raw Markdown. USD costs are recomputed live on every fetch (token mode only — per-call rates are fixed at signing).

```bash
curl https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-001.md
```

---

### POST /contracts/{contract_id}/notarize
Submit to the Town Notary (external service — stellarminds.ai). This agent handles the full loop automatically.

```bash
curl -X POST https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-001/notarize
```

**What happens internally:**
1. Builds a signed Ed25519 sm-conformance badge from the contract hash
2. Submits to `POST https://town-notary-production.up.railway.app/register`
3. Records `notary_signature_id`, `notary_timestamp`, `notary_did_key` on the contract
4. Sets contract `status` to `executed`

**Response (success):**
```json
{
  "contract_id": "A2A-20260629-001",
  "status": "executed",
  "notary_signature_id": "did:key:z6Mk...",
  "notary_timestamp": "2026-06-29T14:30:00Z",
  "notary_did_key": "did:key:z6MkknmHuypD52Dd4HSFKhwWmCZ4yS57qx6DbaFdzSbj2o3X",
  "notary_method": "lab",
  "contract_url": "https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-001.md",
  "notary_inspect_url": "https://town-notary-production.up.railway.app/inspect?runtime=a2a-20260629-001"
}
```

Note: the notary registers using a lowercased runtime ID. Use the `notary_inspect_url` from the response directly.

---

### POST /contracts/{contract_id}/accept
Client agent signs and accepts the contract.

```bash
curl -X POST https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-001/accept \
  -H "Content-Type: application/json" \
  -d '{
    "accepting_agent": "client-agent/1.0",
    "accepting_human": "Human representative name",
    "action": "accepted"
  }'
```

---

### GET /contracts/{contract_id}/status
Check status and whether the Notary has countersigned.

**Response:**
```json
{
  "contract_id": "A2A-20260629-001",
  "status": "executed",
  "notary_countersigned": true,
  "notary_signature_id": "did:key:z6Mk...",
  "contract_url": "https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-001.md"
}
```

---

### GET /contracts
List all contracts on this agent.

---

### GET /agent.json
Machine-readable identity card — lists all endpoints, the live Pricing Scraper URL, and the Town Notary block.

---

## Pricing model — token mode

Token fields are computed once at generation and stored statically. USD is recomputed live on every `GET /contracts/{id}.md` using the current Pricing Scraper rate.

```
token_estimate  = requested_tokens × tier_multiplier   [static]
followup_budget = token_estimate × 20%                  [static]
price_cap       = (token_estimate + followup_budget) / 0.75  [static — hard ceiling]
upcharge_tokens = token_estimate × upcharge_pct         [static — 5–25% band]
skill_premium   = skill_premium_tokens × tier_multiplier [static]
total_tokens    = price_cap + upcharge_tokens + skill_premium + materials  [static]
total_usd       = total_tokens × live_rate_per_1k / 1000  [live on every read]
```

**Three auto-generated tiers:**

| Tier | Token multiplier | Upcharge default | Skill multiplier | Revisions |
|---|---:|---:|---:|---:|
| Starter | × 0.6 | 5% | × 0.5 | 1 |
| Standard | × 1.0 | 12% | × 1.0 | 3 |
| Premium | × 1.5 | 25% | × 1.5 | 5 |

---

## Pricing model — per-call mode

Provider sets a fixed USD price per API call. Rate is locked at signing — the provider absorbs model cost variability.

**What counts as one call:** A single HTTP request to the provider's endpoint that results in a processed response. Provider-side retries do not count. Client-initiated retries count as new calls.

**Bundle rules:** Unused calls expire at end of validity period. Bundles are non-refundable once consumed past 10%.

**Payment:** Pay-as-you-go billed weekly or on reaching a $10 minimum. Bundles billed in full at signing; overage billed weekly.

---

## Pricing Scraper integration

Live token rates are fetched from the **LLM Pricing Scraper**:

**Base URL:** `https://pricing-scraper-production-cd54.up.railway.app`

| Endpoint | Purpose |
|---|---|
| `GET /skill.md` | Scraper's own skill doc |
| `GET /pricing/models` | All models from all providers |
| `GET /pricing/models?provider=anthropic` | Filter by provider |
| `GET /pricing/models?family=gpt` | Filter by family |
| `GET /pricing/models/{model_id}` | Single model — `input_per_1k_usd`, `output_per_1k_usd` |
| `GET /scrape/status` | Last scrape timestamp and per-provider health |
| `POST /scrape/run` | Trigger a manual scrape |

**Blended rate formula (60% input + 40% output):**
```bash
curl https://pricing-scraper-production-cd54.up.railway.app/pricing/models/claude-haiku-4-5
# → { "input_per_1k_usd": 0.001, "output_per_1k_usd": 0.005 }
# blended = 0.001 * 0.6 + 0.005 * 0.4 = 0.0026 USD/1k tokens
```

**Fallback:** If the scraper is unreachable, the contract agent uses a built-in rate table and sets `rate_is_live: false` in the response. Per-call contracts are not affected — their rates are fixed at signing.

---

## Town Notary integration

External service operated by stellarminds.ai — not deployed by this project.

**Base URL:** `https://town-notary-production.up.railway.app`

| Endpoint | What it does |
|---|---|
| `POST /register` | Register a signed conformance badge (primary path) |
| `POST /countersign` | Issue a Notary rung-2 stamp |
| `GET /register` | List all certified runtimes |
| `GET /inspect?runtime={id}` | Look up one contract before transacting |
| `POST /verify` | Verify a badge offline (read-only) |

**Before paying — always verify:**
```bash
curl "https://town-notary-production.up.railway.app/inspect?runtime=a2a-20260629-001"
# { "certified": true, ... }  → safe to transact
# { "detail": "not on the register" }  → do NOT release payment
```

Note: the inspect `runtime` parameter is the contract ID lowercased.

---

## How an agent should use this skill

### Token-mode workflow

1. **Generate:**
   ```bash
   curl -X POST https://hackathon-contract-agent-production.up.railway.app/contracts/generate \
     -H "Content-Type: application/json" \
     -d '{ "pricing_mode": "token", "token_estimate": 50000, ... }'
   ```

2. **Read (live USD):**
   ```bash
   curl https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-001.md
   ```

3. **Notarize:**
   ```bash
   curl -X POST https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-001/notarize
   ```

4. **Accept:**
   ```bash
   curl -X POST https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-001/accept \
     -H "Content-Type: application/json" \
     -d '{"accepting_agent": "client/1.0", "accepting_human": "Alice", "action": "accepted"}'
   ```

5. **Verify before paying:**
   ```bash
   curl "https://town-notary-production.up.railway.app/inspect?runtime=a2a-20260629-001"
   ```

### Per-call workflow

Same steps — the only difference is the generate body:
```bash
curl -X POST https://hackathon-contract-agent-production.up.railway.app/contracts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "pricing_mode": "per_call",
    "package": "Growth",
    "per_call_tiers": [
      { "name": "Pay-as-you-go", "per_call_usd": 0.75, "call_limit": null, "features": ["48h SLA"] },
      { "name": "Growth", "per_call_usd": 0.55, "call_limit": 50, "features": ["24h SLA"],
        "bundle": { "name": "20-post pack", "calls": 20, "price_usd": 9.00,
                    "per_call_usd": 0.45, "overage_per_call_usd": 0.55, "validity_days": 60 } }
    ],
    ...
  }'
```

---

## Reference docs

| Doc | URL |
|---|---|
| Contract template | `GET /reference/contract-template` |
| Pricing guide | `GET /reference/pricing-guide` |
| Pricing Scraper integration | `GET /reference/pricing-scraper-integration` |
| Notary integration | `GET /reference/notary-integration` |
| Submission guidelines | `GET /reference/submission-guidelines` |
