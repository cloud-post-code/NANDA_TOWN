# Hackathon Contract Agent

Generate, fill, and notarize A2A service contracts priced on an agent token premium system. Built at the Nanda Town Hackathon. Exposes the finished contract as a `.md` file any other agent can fetch, inspect, and sign.

## Base URL

https://hackathon-contract-agent-production.up.railway.app

## What it does

An agent calls this skill to:
1. **Generate** a filled A2A service contract for a hackathon-built service offering
2. **Price** the engagement using the token-premium pricing model (tokens + skill premium + service upcharge)
3. **Send the contract to the Town Notary** for countersignature — call `POST /contracts/{id}/notarize`
4. **Expose the executed contract** as a stable `.md` URL other agents can fetch

The contract follows the `a2a_contract_version: "0.2"` format and is machine-readable by any OpenClaw-compatible agent.

---

## Endpoints

### POST /contracts/generate
Create a new draft contract for a hackathon service offering.

Before calling this, fetch the live model rate from the Pricing Scraper:
```bash
curl https://pricing-scraper-production.up.railway.app/pricing/models/claude-sonnet-4-6
# → { "input_per_1k_usd": 0.003, "output_per_1k_usd": 0.015, ... }
# blended = input * 0.6 + output * 0.4  ← use to validate your token_estimate USD cost
```
The contract agent fetches this automatically — you do not need to pass the rate. The scraper provides the per-token rate only; all pricing math (price_cap, tiers, upcharge) runs inside this agent.

**Body (JSON):**
```json
{
  "service_name": "The name of your hackathon-built service",
  "provider_agent": "Your agent name and version",
  "provider_endpoint": "https://your-agent.example.com",
  "provider_human": "Your name or team name",
  "provider_legal_name": "Legal entity name (optional)",
  "client_agent": "Calling agent name/version",
  "client_endpoint": "https://client-agent.example.com",
  "client_human": "Client representative name",
  "client_legal_name": "Client legal entity (optional)",
  "package": "starter | standard | premium",
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
  "token_estimate": 50000,
  "skill_premium_tokens": 10000,
  "skill_premium_justification": "Why the skill is worth more than raw tokens",
  "upcharge_pct": 0.12,
  "materials_estimate": 0,
  "currency": "tokens | USD | credits",
  "ip_model": "client_ownership | provider_license | open",
  "human_review_required": true,
  "governing_jurisdiction": "California, USA",
  "questions": {
    "who_do_you_help": "Who is the target user or agent",
    "what_do_you_deliver": "Concrete output description",
    "what_are_you_accessing": "APIs, data, or systems touched",
    "are_there_deliverable_questions": "Any open scope questions",
    "standard_policy": "Any platform or safety policy that applies",
    "appropriation_policy": "IP or data reuse constraints"
  }
}
```

**Response:**
```json
{
  "contract_id": "A2A-20260629-001",
  "status": "draft",
  "contract_url": "https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-001.md",
  "rate_is_live": true,
  "notary_status": "pending",
  "next_step": "POST https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-001/notarize"
}
```

`rate_is_live: true` means the USD cost in Section 4 used a live rate from the Pricing Scraper. `false` means the fallback table was used (scraper unreachable).

---

### GET /contracts/{contract_id}.md
Fetch the filled contract as a raw Markdown file. This is the machine-readable artifact other agents consume.

```bash
GET https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-001.md
```

Response: Raw `.md` with all fields filled, pricing computed, and (once notarized) the Notary countersignature in Section 12.

---

### POST /contracts/{contract_id}/notarize
Submit the contract to the Town Notary for countersignature. This agent handles the full Notary loop — you do not call the Notary directly.

**Body:** Empty — contract_id in the path is sufficient.

```bash
curl -X POST https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-001/notarize
```

**What happens:**
1. Builds a conformance badge envelope from the contract hash (`suite_digest: sha256:{hash}`)
2. POSTs to `https://town-notary-production.up.railway.app/countersign` with `method: "lab"`
3. Falls back to `POST /register` if countersign is refused
4. Records `notary_signature_id`, `notary_timestamp`, `notary_did_key`, `notary_method` on the contract
5. Sets contract `status` to `executed`

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
  "notary_inspect_url": "https://town-notary-production.up.railway.app/inspect?runtime=A2A-20260629-001"
}
```

**Response (notary refused/unreachable):**
```json
{
  "contract_id": "A2A-20260629-001",
  "status": "sealed",
  "notary_status": "failed",
  "error": "HTTP 422: ...",
  "hint": "The Town Notary refused or was unreachable. ..."
}
```

**Town Notary direct endpoints (for manual verification only — do not call these yourself):**
```bash
# Verify a contract is on the register before paying
curl "https://town-notary-production.up.railway.app/inspect?runtime=A2A-20260629-001"

# See all registered runtimes
curl "https://town-notary-production.up.railway.app/register"
```

---

### GET /contracts/{contract_id}/status
Check contract status and notary countersignature.

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

### POST /contracts/{contract_id}/seal
Mark a contract as sealed and ready for notarization.

**Body:** Empty.

**Response:**
```json
{
  "contract_id": "A2A-20260629-001",
  "status": "sealed",
  "contract_url": "...",
  "next_step": "POST .../notarize"
}
```

---

### POST /contracts/{contract_id}/accept
Client agent records acceptance. Sets status to `accepted` in the Agent Confirmation Record (Section 13).

**Body:**
```json
{
  "accepting_agent": "client-agent-name/version",
  "accepting_human": "Human representative name",
  "action": "accepted"
}
```

---

### GET /contracts
List all contracts generated by this agent.

**Response:**
```json
{
  "count": 3,
  "contracts": [
    {
      "contract_id": "A2A-20260629-001",
      "service_name": "Survey Answering Service",
      "status": "executed",
      "contract_url": "https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-001.md"
    }
  ]
}
```

---

### GET /agent.json
Machine-readable agent identity card for A2A discovery. Includes notary and pricing_scraper block with all endpoints.

---

## Pricing model — token premium system

The contract enforces a **four-layer pricing model**. The Pricing Scraper supplies only the per-token rate; all math runs inside this agent.

```
token_estimate  = requested_tokens × tier_multiplier
followup_budget = token_estimate × 20%
price_cap       = (token_estimate + followup_budget) / 0.75
  — invariant: estimate + followup = 75% of cap (25% buffer before change request required)
upcharge_tokens = token_estimate × upcharge_pct  (5–25% band)
skill_premium   = skill_premium_tokens × tier_multiplier
total_tokens    = price_cap + upcharge_tokens + skill_premium + materials
total_usd       = total_tokens × rate_per_1k_usd / 1000
```

| Layer | What it is | How it's set |
|---|---|---|
| **Token estimate** | Assumed LLM + tool compute to deliver the service | Caller sets `token_estimate`; tier multiplier applied |
| **Follow-up budget** | Reserved tokens for second-round revisions (20% of estimate) | Auto-computed; drives price_cap |
| **Price cap** | Hard ceiling — no additional billing without a change request | `(estimate + followup) / 0.75` |
| **Service premium** | 5–25% upcharge on the estimate (infra, reliability, priority) | `upcharge_pct` param or tier default |
| **Skill premium** | Value of the agent's capability above raw tokens | Caller sets `skill_premium_tokens` |
| **Materials** | Third-party licenses, paid APIs, cloud infra | Caller sets `materials_estimate`; >500 tokens requires pre-approval |

**Rate lookup:** The agent calls `GET /pricing/models/{model_id}` on the Pricing Scraper to get live `input_per_1k_usd` and `output_per_1k_usd`, then blends them (60% input + 40% output). If the scraper is unreachable, the built-in fallback table is used and `rate_is_live: false` is returned.

---

## Offer menu — three tiers auto-generated

| Tier | Token estimate multiplier | Upcharge default | Skill mult | Revisions |
|---|---:|---:|---:|---:|
| Starter | × 0.6 | 5% | × 0.5 | 1 |
| Standard | × 1.0 | 12% | × 1.0 | 3 |
| Premium | × 1.5 | 25% | × 1.5 | 5 |

Client selects one at acceptance. Safety, privacy, and minimum payment are never negotiable.

---

## Pricing Scraper integration

Token rates are fetched from **LLM Pricing Scraper** (`https://pricing-scraper-production.up.railway.app`). The scraper scrapes Anthropic, OpenAI, Google, Together AI (Llama), and ZhipuAI (GLM) pricing pages daily.

**The scraper's role is rate lookup only.** It does not compute price_cap, upcharge, or any other contract math.

| Endpoint | Purpose |
|---|---|
| `GET /pricing/models` | All models from all providers |
| `GET /pricing/models?provider=anthropic` | Filter by provider |
| `GET /pricing/models?family=gpt` | Filter by family |
| `GET /pricing/models/{model_id}` | Single model — returns `input_per_1k_usd`, `output_per_1k_usd` |
| `GET /scrape/status` | When data was last refreshed |

**Fallback:** If the Pricing Scraper is unreachable, the contract agent uses its built-in `MODEL_RATES_FALLBACK` table and sets `rate_is_live: false` in the response.

See `reference/pricing-scraper-integration.md` for full endpoint reference.

---

## Town Notary integration

Every executed contract goes through **The Town Notary** (`https://town-notary-production.up.railway.app`) for countersignature. Call `POST /contracts/{id}/notarize` on this agent — it handles the Notary loop automatically.

**Town Notary endpoints (informational — this agent calls them for you):**

| Endpoint | What it does |
|---|---|
| `POST /verify` | Verify a signed conformance badge offline |
| `POST /countersign` | Issue a Notary rung-2 stamp on a passing badge |
| `POST /register` | Register a passing badge in the public ledger |
| `GET /register` | List all certified runtimes |
| `GET /inspect?runtime={id}` | Look up one contract's standing before transacting |

**Before paying — always verify:**
```bash
curl "https://town-notary-production.up.railway.app/inspect?runtime=A2A-20260629-001"
# Returns: { "certified": true, "runtime": "A2A-20260629-001", ... }
# or: { "detail": "not on the register" }  ← do NOT release payment
```

The Notary expects a signed sm-conformance badge envelope. This agent constructs and submits the badge automatically from the contract hash.

See `reference/notary-integration.md` for the badge format and error handling.

---

## How an agent should use this skill

1. **Fetch live token rates** (optional — the agent does this automatically):
   ```bash
   curl https://pricing-scraper-production.up.railway.app/pricing/models/claude-sonnet-4-6
   ```

2. **Generate the contract:**
   ```bash
   curl -X POST https://hackathon-contract-agent-production.up.railway.app/contracts/generate \
     -H "Content-Type: application/json" \
     -d '{ "service_name": "...", "token_estimate": 50000, ... }'
   ```
   Check `rate_is_live` in the response — if `false`, USD estimates used fallback rates.

3. **Review the filled contract:**
   ```bash
   curl https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-001.md
   ```

4. **Notarize (required before binding):**
   ```bash
   curl -X POST https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-001/notarize
   ```

5. **Client accepts:**
   ```bash
   curl -X POST https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-001/accept \
     -H "Content-Type: application/json" \
     -d '{"accepting_agent": "client/1.0", "accepting_human": "Alice", "action": "accepted"}'
   ```

6. **Verify before paying:**
   ```bash
   curl "https://town-notary-production.up.railway.app/inspect?runtime=A2A-20260629-001"
   ```

---

## Reference

- `reference/contract-template.md` — The filled A2A contract template this skill outputs
- `reference/pricing-guide.md` — How to set skill_premium_tokens, token_estimate, and understand pricing math
- `reference/pricing-scraper-integration.md` — Pricing Scraper endpoints, live rate lookup, blended-rate formula
- `reference/notary-integration.md` — Town Notary badge format, endpoint details, and error handling
- `reference/submission-guidelines.md` — How to submit this skill to the Nanda Town registry
