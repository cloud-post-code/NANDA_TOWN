import hashlib
import os
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel

# ── LLM Pricing catalog ───────────────────────────────────────────────────────
# Prices in USD per 1M tokens. Updated manually; source links in each entry.
# Llama and GLM are open-source so we list typical hosted-API prices (e.g. Together AI / ZhipuAI).

_LLM_PRICING: list[dict] = [
    # ── Anthropic Claude ──────────────────────────────────────────────────────
    {
        "provider": "Anthropic",
        "family": "Claude",
        "model": "claude-opus-4-8",
        "display_name": "Claude Opus 4.8",
        "input_per_1m_usd": 5.00,
        "output_per_1m_usd": 25.00,
        "context_window_k": 1000,
        "notes": "Most capable Opus-tier model",
        "source": "https://www.anthropic.com/pricing",
    },
    {
        "provider": "Anthropic",
        "family": "Claude",
        "model": "claude-opus-4-7",
        "display_name": "Claude Opus 4.7",
        "input_per_1m_usd": 5.00,
        "output_per_1m_usd": 25.00,
        "context_window_k": 1000,
        "notes": "Previous-generation Opus",
        "source": "https://www.anthropic.com/pricing",
    },
    {
        "provider": "Anthropic",
        "family": "Claude",
        "model": "claude-sonnet-4-6",
        "display_name": "Claude Sonnet 4.6",
        "input_per_1m_usd": 3.00,
        "output_per_1m_usd": 15.00,
        "context_window_k": 1000,
        "notes": "Best speed/intelligence balance",
        "source": "https://www.anthropic.com/pricing",
    },
    {
        "provider": "Anthropic",
        "family": "Claude",
        "model": "claude-haiku-4-5",
        "display_name": "Claude Haiku 4.5",
        "input_per_1m_usd": 1.00,
        "output_per_1m_usd": 5.00,
        "context_window_k": 200,
        "notes": "Fastest and most cost-effective",
        "source": "https://www.anthropic.com/pricing",
    },
    {
        "provider": "Anthropic",
        "family": "Claude",
        "model": "claude-fable-5",
        "display_name": "Claude Fable 5",
        "input_per_1m_usd": 10.00,
        "output_per_1m_usd": 50.00,
        "context_window_k": 1000,
        "notes": "Most capable widely released Claude model",
        "source": "https://www.anthropic.com/pricing",
    },
    # ── OpenAI GPT ───────────────────────────────────────────────────────────
    {
        "provider": "OpenAI",
        "family": "GPT",
        "model": "gpt-4o",
        "display_name": "GPT-4o",
        "input_per_1m_usd": 2.50,
        "output_per_1m_usd": 10.00,
        "context_window_k": 128,
        "notes": "Flagship multimodal model",
        "source": "https://openai.com/api/pricing/",
    },
    {
        "provider": "OpenAI",
        "family": "GPT",
        "model": "gpt-4o-mini",
        "display_name": "GPT-4o mini",
        "input_per_1m_usd": 0.15,
        "output_per_1m_usd": 0.60,
        "context_window_k": 128,
        "notes": "Cost-efficient small model",
        "source": "https://openai.com/api/pricing/",
    },
    {
        "provider": "OpenAI",
        "family": "GPT",
        "model": "gpt-4-turbo",
        "display_name": "GPT-4 Turbo",
        "input_per_1m_usd": 10.00,
        "output_per_1m_usd": 30.00,
        "context_window_k": 128,
        "notes": "High-capability with vision",
        "source": "https://openai.com/api/pricing/",
    },
    {
        "provider": "OpenAI",
        "family": "GPT",
        "model": "o1",
        "display_name": "o1",
        "input_per_1m_usd": 15.00,
        "output_per_1m_usd": 60.00,
        "context_window_k": 200,
        "notes": "Reasoning model",
        "source": "https://openai.com/api/pricing/",
    },
    {
        "provider": "OpenAI",
        "family": "GPT",
        "model": "o3-mini",
        "display_name": "o3-mini",
        "input_per_1m_usd": 1.10,
        "output_per_1m_usd": 4.40,
        "context_window_k": 200,
        "notes": "Cost-efficient reasoning model",
        "source": "https://openai.com/api/pricing/",
    },
    # ── Google Gemini ─────────────────────────────────────────────────────────
    {
        "provider": "Google",
        "family": "Gemini",
        "model": "gemini-2.5-pro",
        "display_name": "Gemini 2.5 Pro",
        "input_per_1m_usd": 1.25,
        "output_per_1m_usd": 10.00,
        "context_window_k": 1000,
        "notes": "Most capable Gemini; ≤200k tokens input price shown",
        "source": "https://ai.google.dev/pricing",
    },
    {
        "provider": "Google",
        "family": "Gemini",
        "model": "gemini-2.5-flash",
        "display_name": "Gemini 2.5 Flash",
        "input_per_1m_usd": 0.075,
        "output_per_1m_usd": 0.30,
        "context_window_k": 1000,
        "notes": "Fast and cost-efficient",
        "source": "https://ai.google.dev/pricing",
    },
    {
        "provider": "Google",
        "family": "Gemini",
        "model": "gemini-1.5-pro",
        "display_name": "Gemini 1.5 Pro",
        "input_per_1m_usd": 1.25,
        "output_per_1m_usd": 5.00,
        "context_window_k": 2000,
        "notes": "Long-context; ≤128k tokens price shown",
        "source": "https://ai.google.dev/pricing",
    },
    {
        "provider": "Google",
        "family": "Gemini",
        "model": "gemini-1.5-flash",
        "display_name": "Gemini 1.5 Flash",
        "input_per_1m_usd": 0.075,
        "output_per_1m_usd": 0.30,
        "context_window_k": 1000,
        "notes": "Speed-optimized; ≤128k price shown",
        "source": "https://ai.google.dev/pricing",
    },
    # ── Meta Llama (via Together AI hosted API) ───────────────────────────────
    {
        "provider": "Meta (hosted: Together AI)",
        "family": "Llama",
        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "display_name": "Llama 3.3 70B Instruct Turbo",
        "input_per_1m_usd": 0.88,
        "output_per_1m_usd": 0.88,
        "context_window_k": 128,
        "notes": "Open-source; price from Together AI hosted API",
        "source": "https://www.together.ai/pricing",
    },
    {
        "provider": "Meta (hosted: Together AI)",
        "family": "Llama",
        "model": "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
        "display_name": "Llama 3.1 405B Instruct Turbo",
        "input_per_1m_usd": 3.50,
        "output_per_1m_usd": 3.50,
        "context_window_k": 128,
        "notes": "Largest open-source Llama; Together AI hosted price",
        "source": "https://www.together.ai/pricing",
    },
    {
        "provider": "Meta (hosted: Together AI)",
        "family": "Llama",
        "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "display_name": "Llama 3.1 8B Instruct Turbo",
        "input_per_1m_usd": 0.18,
        "output_per_1m_usd": 0.18,
        "context_window_k": 128,
        "notes": "Lightweight open-source; Together AI hosted price",
        "source": "https://www.together.ai/pricing",
    },
    # ── Zhipu GLM (via ZhipuAI hosted API) ───────────────────────────────────
    {
        "provider": "Zhipu AI",
        "family": "GLM",
        "model": "glm-4-plus",
        "display_name": "GLM-4 Plus",
        "input_per_1m_usd": 0.70,
        "output_per_1m_usd": 0.70,
        "context_window_k": 128,
        "notes": "Flagship GLM-4 from Zhipu AI (CNY pricing converted at ~7.2 CNY/USD)",
        "source": "https://open.bigmodel.cn/pricing",
    },
    {
        "provider": "Zhipu AI",
        "family": "GLM",
        "model": "glm-4",
        "display_name": "GLM-4",
        "input_per_1m_usd": 0.14,
        "output_per_1m_usd": 0.14,
        "context_window_k": 128,
        "notes": "Standard GLM-4 (CNY pricing converted at ~7.2 CNY/USD)",
        "source": "https://open.bigmodel.cn/pricing",
    },
    {
        "provider": "Zhipu AI",
        "family": "GLM",
        "model": "glm-4-flash",
        "display_name": "GLM-4 Flash",
        "input_per_1m_usd": 0.0,
        "output_per_1m_usd": 0.0,
        "context_window_k": 128,
        "notes": "Free tier model from Zhipu AI",
        "source": "https://open.bigmodel.cn/pricing",
    },
]

def _build_pricing_response() -> dict:
    """Group the static catalog by provider+family and compute per-1k-token rates."""
    by_family: dict[str, list] = {}
    for m in _LLM_PRICING:
        key = f"{m['provider']} / {m['family']}"
        entry = {
            "model": m["model"],
            "display_name": m["display_name"],
            "input_per_1m_tokens_usd": m["input_per_1m_usd"],
            "output_per_1m_tokens_usd": m["output_per_1m_usd"],
            "input_per_1k_tokens_usd": round(m["input_per_1m_usd"] / 1000, 8),
            "output_per_1k_tokens_usd": round(m["output_per_1m_usd"] / 1000, 8),
            "context_window_k": m["context_window_k"],
            "notes": m.get("notes", ""),
            "source": m.get("source", ""),
        }
        by_family.setdefault(key, []).append(entry)

    families = []
    for key, models in by_family.items():
        provider, family = key.split(" / ", 1)
        families.append({
            "provider": provider,
            "family": family,
            "models": models,
        })

    return {
        "as_of": "2025-06-29",
        "currency": "USD",
        "note": (
            "Prices are sourced from public provider pricing pages. "
            "Llama prices reflect Together AI hosted API rates. "
            "GLM prices are converted from CNY at ~7.2 CNY/USD. "
            "Always verify current rates at the source URLs before billing."
        ),
        "families": families,
        "all_models": [
            {
                "provider": m["provider"],
                "family": m["family"],
                "model": m["model"],
                "display_name": m["display_name"],
                "input_per_1m_tokens_usd": m["input_per_1m_usd"],
                "output_per_1m_tokens_usd": m["output_per_1m_usd"],
                "input_per_1k_tokens_usd": round(m["input_per_1m_usd"] / 1000, 8),
                "output_per_1k_tokens_usd": round(m["output_per_1m_usd"] / 1000, 8),
                "context_window_k": m["context_window_k"],
                "notes": m.get("notes", ""),
                "source": m.get("source", ""),
            }
            for m in _LLM_PRICING
        ],
    }

app = FastAPI(title="Hackathon Contract Agent", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NOTARY_BASE = "https://town-notary-production.up.railway.app"
SELF_BASE = os.getenv("SELF_BASE_URL", "https://hackathon-contract-agent-production.up.railway.app")

# Stable agent identifier — persisted in /tmp across restarts within a deployment
_ID_PATH = Path("/tmp/agent_id.txt")

def _load_or_create_agent_id() -> str:
    if _ID_PATH.exists():
        return _ID_PATH.read_text().strip()
    agent_id = f"urn:uuid:{uuid.uuid4()}"
    _ID_PATH.write_text(agent_id)
    return agent_id

_AGENT_ID = _load_or_create_agent_id()


# In-memory store (replace with a DB for production)
_contracts: dict[str, dict] = {}


# ── Request models ────────────────────────────────────────────────────────────

class Deliverable(BaseModel):
    name: str
    format: str
    due_date: str
    acceptance_criteria: str
    revisions_included: int = 2


class Questions(BaseModel):
    who_do_you_help: str = ""
    what_do_you_deliver: str = ""
    what_are_you_accessing: str = ""
    are_there_deliverable_questions: str = "None"
    standard_policy: str = "Nanda Town platform policy"
    appropriation_policy: str = "Client owns custom deliverables on full payment"


class GenerateRequest(BaseModel):
    service_name: str
    provider_agent: str
    provider_endpoint: str
    provider_human: str
    provider_legal_name: str = ""
    client_agent: str = "unknown-client/1.0"
    client_endpoint: str = ""
    client_human: str = ""
    client_legal_name: str = ""
    package: str = "standard"
    smart_goal: str
    in_scope: list[str]
    out_of_scope: list[str] = []
    deliverables: list[Deliverable]
    model: str = "claude-sonnet-4-6"
    token_estimate: int
    skill_premium_tokens: int
    skill_premium_justification: str = "Saves manual prompt engineering effort"
    upcharge_pct: float | None = None  # 0.05–0.20; auto-set from tier if None
    materials_estimate: int = 0
    currency: str = "tokens"
    ip_model: str = "client_ownership"
    human_review_required: bool = True
    governing_jurisdiction: str = "California, USA"
    questions: Questions = Questions()


class AcceptRequest(BaseModel):
    accepting_agent: str
    accepting_human: str = ""
    action: str = "accepted"


# ── Pricing helpers ───────────────────────────────────────────────────────────

# Per-model token rates (USD per 1k tokens, blended input+output estimate)
MODEL_RATES = {
    "claude-sonnet-4-6":  0.0045,
    "claude-opus-4-8":    0.0225,
    "claude-haiku-4-5":   0.00045,
    "gpt-4o":             0.005,
    "gpt-4o-mini":        0.00030,
    "gemini-1.5-pro":     0.00350,
    "gemini-2.0-flash":   0.00050,
    "default":            0.0045,
}

# Upcharge % bands by service complexity (5–25% range)
UPCHARGE_BANDS = {
    "starter":  0.05,   # 5%  — simple, low-risk
    "standard": 0.12,   # 12% — typical engagement
    "premium":  0.25,   # 25% — high complexity / priority
}


def _compute_tiers(token_est: int, skill_premium: int, materials: int, model: str, upcharge_pct: float | None):
    rate_per_1k = MODEL_RATES.get(model, MODEL_RATES["default"])

    tier_configs = {
        "starter":  {"multiplier": 0.6,  "skill_mult": 0.5,  "revisions": 1, "label": "Core deliverable only"},
        "standard": {"multiplier": 1.0,  "skill_mult": 1.0,  "revisions": 3, "label": "Core + follow-up refinements"},
        "premium":  {"multiplier": 1.5,  "skill_mult": 1.5,  "revisions": 5, "label": "Full scope + priority turnaround"},
    }

    tiers = {}
    for name, cfg in tier_configs.items():
        # token_estimate: assumed cost to complete the agreed deliverable
        token_estimate    = int(token_est * cfg["multiplier"])
        pct               = upcharge_pct if upcharge_pct is not None else UPCHARGE_BANDS[name]
        # clamp premium to 5–25%
        pct               = max(0.05, min(0.25, pct))
        upcharge_tokens   = int(token_estimate * pct)

        # price_cap: max tokens user pays to receive agreed deliverable
        # price_cap must be > token_estimate + followup_budget (followups + estimate = 75% of cap)
        # So: token_estimate + followup_budget = 0.75 × price_cap
        # → price_cap = (token_estimate + followup_budget) / 0.75
        # We derive followup_budget as a fraction of token_estimate (20% default), then solve for cap.
        followup_budget   = int(token_estimate * 0.20)
        # price_cap satisfies: estimate + followups = 75% of cap  →  cap = (est + followups) / 0.75
        price_cap         = int((token_estimate + followup_budget) / 0.75)

        sp                = int(skill_premium * cfg["skill_mult"])
        total_tokens      = price_cap + sp + materials + upcharge_tokens
        usd_cost          = round(total_tokens * rate_per_1k / 1000, 4)

        tiers[name] = {
            "model":            model,
            "rate_per_1k_usd":  rate_per_1k,
            "token_estimate":   token_estimate,      # assumed cost for the deliverable
            "followup_budget":  followup_budget,     # tokens reserved for second-round follow-ups
            "price_cap":        price_cap,           # max tokens to receive agreed deliverable (est+followups = 75% of cap)
            "upcharge_pct":     pct,                 # premium factor (5–25%)
            "upcharge_tokens":  upcharge_tokens,     # tokens added as premium upcharge
            "skill_premium":    sp,
            "materials":        materials,
            "total_tokens":     total_tokens,        # price_cap + upcharge + skill_premium + materials
            "total_usd":        usd_cost,
            "revisions":        cfg["revisions"],
            "label":            cfg["label"],
            # legacy aliases kept for backward compat
            "base_tokens":      token_estimate,
            "billed_tokens":    price_cap + upcharge_tokens,
            "cap":              price_cap,
            "total":            total_tokens,
        }
    return tiers


# ── Contract rendering ────────────────────────────────────────────────────────

def _render_contract(data: dict) -> str:
    r = data
    tiers = r["tiers"]
    pkg = r["package"].lower()
    selected_tier = tiers.get(pkg, tiers["standard"])

    ip_ownership_line = ""
    if r["ip_model"] == "client_ownership":
        ip_ownership_line = "- [x] **Client ownership on payment.** Upon full payment, Provider assigns to Client all rights in custom deliverables."
    elif r["ip_model"] == "provider_license":
        ip_ownership_line = "- [x] **Provider license.** Provider retains ownership; grants Client a non-exclusive, perpetual, commercial license."
    else:
        ip_ownership_line = "- [x] **Open license.** Final deliverables released under MIT License."

    deliverables_table = "\n".join(
        f"| `{d['name']}` | `{d['format']}` | `{d['due_date']}` | `{d['acceptance_criteria']}` | {d['revisions_included']} |"
        for d in r["deliverables"]
    )

    in_scope_lines = "\n".join(f"- {item}" for item in r["in_scope"])
    out_of_scope_lines = "\n".join(f"- {item}" for item in r["out_of_scope"]) or "- None specified"
    min_outcomes = "\n".join(
        f"- `{d['name']}` accepted: {d['acceptance_criteria']}" for d in r["deliverables"]
    )

    notary_section = f"""| Notary signature ID | `{r.get('notary_signature_id', 'pending — call /notarize')}` |
| Notary timestamp | `{r.get('notary_timestamp', 'pending')}` |
| Contract hash (SHA-256) | `{r['contract_hash']}` |
| Notary inspect URL | `{NOTARY_BASE}/inspect?runtime={r['contract_id']}` |
| Notary public key (did:key) | `{r.get('notary_did_key', 'pending')}` |"""

    client_action = r.get("client_action", "pending")
    client_timestamp = r.get("client_timestamp", "pending")
    client_acceptance_date = r.get("client_acceptance_date", "pending")

    contract_url = f"{SELF_BASE}/contracts/{r['contract_id']}.md"

    return f"""---
a2a_contract_version: "0.2"
contract_id: "{r['contract_id']}"
status: "{r['status']}"
effective_date: "{r['effective_date']}"
expires_on: "{r['expires_on']}"
governing_jurisdiction: "{r['governing_jurisdiction']}"
source_of_truth: "versioned Markdown — {contract_url}"
contract_hash: "{r['contract_hash']}"
human_approval_required: {str(r['human_review_required']).lower()}
human_review_status: "{'required' if r['human_review_required'] else 'not included'}"
---

# A2A Service Contract — {r['service_name']}

> **Built at the Nanda Town Hackathon.** Generated by Hackathon Contract Agent and countersigned by the Town Notary.
>
> **Agent status:** Agents may propose, negotiate, track, and perform work, but may not amend pricing, scope, IP, or liability terms without express authority under Section 13.
>
> **Not legal advice.** Have qualified counsel review before treating this as a binding legal agreement.

---

## 1. Parties, Authority, and Purpose

| Role | Principal | Authorized representative | Agent / system | Endpoint |
|---|---|---|---|---|
| Client | `{r['client_legal_name'] or r['client_human'] or 'TBD'}` | `{r['client_human']}` | `{r['client_agent']}` | `{r['client_endpoint']}` |
| Provider | `{r['provider_legal_name'] or r['provider_human']}` | `{r['provider_human']}` | `{r['provider_agent']}` | `{r['provider_endpoint']}` |

**Purpose.** Provider will deliver `{r['service_name']}`. Client will provide agreed inputs, approvals, and payment.

**Independent contractor.** Provider is an independent contractor, not Client's employee or partner.

---

## 2. Service, Scope, and Success Criteria

- **Service name:** `{r['service_name']}`
- **Package:** `{r['package'].title()}`
- **Start date:** `{r['effective_date']}`
- **Target delivery:** `{r['target_delivery_date']}`

### SMART goal

> {r['smart_goal']}

### In scope

{in_scope_lines}

### Out of scope

{out_of_scope_lines}

### Questions answered at contract creation

| Question | Answer |
|---|---|
| Who do you help? | `{r['questions']['who_do_you_help']}` |
| What do you deliver? | `{r['questions']['what_do_you_deliver']}` |
| What are you accessing? | `{r['questions']['what_are_you_accessing']}` |
| Open deliverable questions? | `{r['questions']['are_there_deliverable_questions']}` |
| Standard policy that applies? | `{r['questions']['standard_policy']}` |
| Appropriation/IP policy? | `{r['questions']['appropriation_policy']}` |

### Minimum observable outcome

{min_outcomes}

---

## 3. Deliverables, Acceptance, and Revisions

| Deliverable | Format | Due date | Acceptance criteria | Revisions |
|---|---|---:|---|---:|
{deliverables_table}

1. Provider delivers through `{r['provider_endpoint']}`.
2. Client must accept or reject within **3 business days** of delivery.
3. Rejection must cite the specific unmet acceptance criterion.
4. If Client neither accepts nor rejects within 3 days, the deliverable is **deemed accepted**.

---

## 4. Pricing, Budget, and Payment — Token Premium System

The total price uses three layers: token/compute estimate, materials, and a skill premium.
A **service upcharge** of {int(selected_tier['upcharge_pct']*100)}% (within the 5–25% band) is applied on top of the token estimate.

**Model:** `{selected_tier['model']}` at `{selected_tier['rate_per_1k_usd']} USD per 1,000 tokens`

**Skill premium justification:** {r['skill_premium_justification']}

### Price components

| Component | Definition | Tokens | USD (est.) |
|---|---|---:|---:|
| **Token estimate** | Assumed cost to complete the agreed deliverable | `{selected_tier['token_estimate']:,}` | `${selected_tier['token_estimate'] * selected_tier['rate_per_1k_usd'] / 1000:.4f}` |
| **Follow-up budget** | Tokens reserved for second-round revisions / clarifications | `{selected_tier['followup_budget']:,}` | `${selected_tier['followup_budget'] * selected_tier['rate_per_1k_usd'] / 1000:.4f}` |
| *(estimate + follow-ups)* | Must equal 75% of price cap | `{selected_tier['token_estimate'] + selected_tier['followup_budget']:,}` | — |
| **Price cap** | Max tokens user pays to receive agreed deliverable | `{selected_tier['price_cap']:,}` | `${selected_tier['price_cap'] * selected_tier['rate_per_1k_usd'] / 1000:.4f}` |
| **Service premium ({int(selected_tier['upcharge_pct']*100)}%)** | Upcharge on token estimate (5–25% band; covers infra, reliability, priority) | `+{selected_tier['upcharge_tokens']:,}` | `+${selected_tier['upcharge_tokens'] * selected_tier['rate_per_1k_usd'] / 1000:.4f}` |
| Skill premium | Capability above raw tokens | `+{selected_tier['skill_premium']:,}` | `+${selected_tier['skill_premium'] * selected_tier['rate_per_1k_usd'] / 1000:.4f}` |
| Materials / third-party | Licenses, APIs, infra (pre-approval required >500 tokens) | `+{r['materials_estimate']:,}` | `+${r['materials_estimate'] * selected_tier['rate_per_1k_usd'] / 1000:.4f}` |
| **Grand total** | price cap + premium + skill + materials | **`{selected_tier['total_tokens']:,} tokens`** | **`${selected_tier['total_usd']:.4f}`** |

**Pricing invariant:** token estimate + follow-up budget = {selected_tier['token_estimate'] + selected_tier['followup_budget']:,} tokens = 75% of price cap ({selected_tier['price_cap']:,}). Provider cannot exceed the price cap without an approved change request.

### Payment terms

- **Currency:** `{r['currency']}`
- **Model:** `{selected_tier['model']}` — `{selected_tier['rate_per_1k_usd']} USD / 1k tokens`
- **Deposit:** 25% of total on signing (non-refundable once work begins)
- **Remaining:** On delivery of final accepted deliverable
- **Payment deadline:** Net 3 calendar days after acceptance

---

## 5. Offer Menu

| Option | Model | Token estimate | Follow-ups | Price cap | Premium | Premium tokens | Skill premium | Total tokens | Est. USD | Revisions |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A — Starter | `{tiers['starter']['model']}` | `{tiers['starter']['token_estimate']:,}` | `{tiers['starter']['followup_budget']:,}` | `{tiers['starter']['price_cap']:,}` | `{int(tiers['starter']['upcharge_pct']*100)}%` | `+{tiers['starter']['upcharge_tokens']:,}` | `+{tiers['starter']['skill_premium']:,}` | `{tiers['starter']['total_tokens']:,}` | `${tiers['starter']['total_usd']:.4f}` | 1 |
| B — Standard | `{tiers['standard']['model']}` | `{tiers['standard']['token_estimate']:,}` | `{tiers['standard']['followup_budget']:,}` | `{tiers['standard']['price_cap']:,}` | `{int(tiers['standard']['upcharge_pct']*100)}%` | `+{tiers['standard']['upcharge_tokens']:,}` | `+{tiers['standard']['skill_premium']:,}` | `{tiers['standard']['total_tokens']:,}` | `${tiers['standard']['total_usd']:.4f}` | 3 |
| C — Premium | `{tiers['premium']['model']}` | `{tiers['premium']['token_estimate']:,}` | `{tiers['premium']['followup_budget']:,}` | `{tiers['premium']['price_cap']:,}` | `{int(tiers['premium']['upcharge_pct']*100)}%` | `+{tiers['premium']['upcharge_tokens']:,}` | `+{tiers['premium']['skill_premium']:,}` | `{tiers['premium']['total_tokens']:,}` | `${tiers['premium']['total_usd']:.4f}` | 5 |

**Column guide:**
- **Token estimate** — assumed tokens to complete the deliverable
- **Follow-ups** — tokens budgeted for second-round revisions (estimate + follow-ups = 75% of price cap)
- **Price cap** — the hard ceiling the user pays to receive the agreed deliverable
- **Premium** — service upcharge % (5–25% band)
- **Est. USD** — dollar cost at `{tiers['standard']['rate_per_1k_usd']} USD/1k tokens`

- **Selected:** `{r['package'].title()}`
- **Negotiable:** Token estimate, timeline, revision count, premium %
- **Not negotiable:** Safety constraints, privacy policy, minimum payment
- **Offer valid until:** `{r['expires_on']}`

---

## 6. Change Management

A written change request is required for: out-of-scope work, new outputs, extra revisions, timeline changes, or budget increases.

1. Client sends request to `{r['provider_endpoint']}`.
2. Provider replies within 24 hours with scope, token, and price impact.
3. No changed work begins without both parties recording approval.

| Change ID | Requested change | Impact | Added cap | Approval |
|---|---|---|---:|---|
| *(none at signing)* | | | | |

---

## 7. AI Tools and Human Review

| System | Use | Client data? | Retention |
|---|---|---|---|
| `{r['provider_agent']}` | `{r['service_name']}` | Necessary data only | Session only |
| Town Notary | Contract countersignature | Contract hash only | Public register |

- **Human review:** `{'required' if r['human_review_required'] else 'not included'}`
- **Escalation trigger:** Confidence below threshold, sensitive data, safety impact

AI outputs may contain errors. Client is responsible for reviewing before high-stakes use.

---

## 8. Confidentiality and Data

- **Permitted data:** Only data necessary for `{r['service_name']}`
- **Prohibited data:** Credentials, health data, payment card data, regulated personal data
- **Retention:** Session only; deleted within 24 hours of delivery
- **Incident notice:** Provider notifies Client within 24 hours of confirmed unauthorized access

Confidentiality obligations continue for 2 years after termination.

---

## 9. Intellectual Property

{ip_ownership_line}

**Provider Background IP** includes `{r['provider_agent']}`'s pre-existing prompts, methods, workflows, and reusable components.

---

## 10. Warranties and Limitations

Provider performs services with reasonable skill consistent with ordinary professional practice.

**Liability cap:** Each party's total liability will not exceed total fees paid under this Agreement.

**No guaranteed business result.** Unless stated in Section 2, Provider does not guarantee downstream outcomes.

---

## 11. Term and Termination

- **Term:** Begins `{r['effective_date']}`; ends when accepted deliverables and payment are complete.
- **Termination for convenience:** Either party may end with 48 hours written notice. Client pays for accepted work.
- **Governing law:** `{r['governing_jurisdiction']}`

---

## 12. Town Notary — Countersignature (Required)

Every contract generated by this skill must be countersigned by the Town Notary before it is binding between agents.

**How to notarize this contract:**
```bash
curl -X POST {SELF_BASE}/contracts/{r['contract_id']}/notarize
```

**How to verify before paying:**
```bash
curl "{NOTARY_BASE}/inspect?runtime={r['contract_id']}"
```

If the Notary returns `registered: false`, the contract is not yet binding. Do not release payment.

### Notary countersignature record

| Field | Value |
|---|---|
{notary_section}

---

## 13. Agent Confirmation Record

| Agent | Action | Timestamp | Contract ID | Hash |
|---|---|---|---|---|
| `{r['client_agent']}` | `{client_action}` | `{client_timestamp}` | `{r['contract_id']}` | `{r['contract_hash'][:16]}...` |
| `{r['provider_agent']}` | `proposed` | `{r['effective_date']}T00:00:00Z` | `{r['contract_id']}` | `{r['contract_hash'][:16]}...` |

---

## 14. Acceptance

Client records acceptance by calling:
```
POST {SELF_BASE}/contracts/{r['contract_id']}/accept
```

| Party | Representative | Acceptance | Date |
|---|---|---|---|
| Client | `{r['client_human'] or 'TBD'}` | `POST /contracts/{r['contract_id']}/accept` | `{client_acceptance_date}` |
| Provider | `{r['provider_human']}` | Contract generated at `{contract_url}` | `{r['effective_date']}` |

---

*Generated by Hackathon Contract Agent · Nanda Town Hackathon 2026*
*Town Notary: {NOTARY_BASE}*
"""


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "Hackathon Contract Agent",
        "version": "1.0.0",
        "docs": "/docs",
        "agent_did": _AGENT_ID,
        "skill": f"{SELF_BASE}/skill.md",
    }


@app.get("/skill.md", response_class=PlainTextResponse)
def serve_skill_md():
    skill_path = Path(__file__).parent.parent / "skills" / "hackathon-contract-agent" / "SKILL.md"
    if skill_path.exists():
        return skill_path.read_text()
    return "SKILL.md not found — see GitHub repo"


@app.get("/contracts")
def list_contracts():
    return {
        "count": len(_contracts),
        "contracts": [
            {
                "contract_id": c["contract_id"],
                "service_name": c["service_name"],
                "status": c["status"],
                "contract_url": f"{SELF_BASE}/contracts/{c['contract_id']}.md",
            }
            for c in _contracts.values()
        ],
    }


@app.post("/contracts/generate", status_code=201)
def generate_contract(req: GenerateRequest):
    contract_id = f"A2A-{date.today().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
    effective_date = date.today().isoformat()
    expires_on = (date.today() + timedelta(days=30)).isoformat()
    target_delivery = (date.today() + timedelta(days=14)).isoformat()

    tiers = _compute_tiers(req.token_estimate, req.skill_premium_tokens, req.materials_estimate, req.model, req.upcharge_pct)

    data: dict[str, Any] = {
        "contract_id": contract_id,
        "status": "draft",
        "effective_date": effective_date,
        "expires_on": expires_on,
        "target_delivery_date": target_delivery,
        "service_name": req.service_name,
        "provider_agent": req.provider_agent,
        "provider_endpoint": req.provider_endpoint,
        "provider_human": req.provider_human,
        "provider_legal_name": req.provider_legal_name,
        "client_agent": req.client_agent,
        "client_endpoint": req.client_endpoint,
        "client_human": req.client_human,
        "client_legal_name": req.client_legal_name,
        "package": req.package,
        "smart_goal": req.smart_goal,
        "in_scope": req.in_scope,
        "out_of_scope": req.out_of_scope,
        "deliverables": [d.model_dump() for d in req.deliverables],
        "model": req.model,
        "upcharge_pct": req.upcharge_pct,
        "token_estimate": req.token_estimate,
        "skill_premium_tokens": req.skill_premium_tokens,
        "skill_premium_justification": req.skill_premium_justification,
        "materials_estimate": req.materials_estimate,
        "currency": req.currency,
        "ip_model": req.ip_model,
        "human_review_required": req.human_review_required,
        "governing_jurisdiction": req.governing_jurisdiction,
        "questions": req.questions.model_dump(),
        "tiers": tiers,
        "contract_hash": "pending",
    }

    # Render once with placeholder hash, then compute real hash and re-render
    rendered = _render_contract(data)
    data["contract_hash"] = hashlib.sha256(rendered.encode()).hexdigest()
    rendered = _render_contract(data)

    _contracts[contract_id] = data

    return {
        "contract_id": contract_id,
        "status": "draft",
        "contract_url": f"{SELF_BASE}/contracts/{contract_id}.md",
        "notary_status": "pending",
        "next_step": f"POST {SELF_BASE}/contracts/{contract_id}/seal when ready, then parties contact Town Notary per Section 12",
    }


@app.get("/contracts/{contract_id}.md")
def get_contract_md(contract_id: str):
    if contract_id not in _contracts:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
    rendered = _render_contract(_contracts[contract_id])
    return Response(content=rendered, media_type="text/markdown")


@app.post("/contracts/{contract_id}/seal")
def seal_contract(contract_id: str):
    """Mark a contract as sealed (ready for parties to loop in the Town Notary).

    The Town Notary is referenced in Section 12 of the contract — parties must
    contact the Notary directly at https://town-notary-production.up.railway.app
    to countersign. This agent does not proxy the Notary.
    """
    if contract_id not in _contracts:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
    contract = _contracts[contract_id]
    contract["status"] = "sealed"
    contract["sealed_at"] = datetime.utcnow().isoformat() + "Z"
    contract_url = f"{SELF_BASE}/contracts/{contract_id}.md"
    return {
        "contract_id": contract_id,
        "status": "sealed",
        "contract_url": contract_url,
        "notary_instructions": (
            "To countersign this contract, the parties must contact the Town Notary directly. "
            f"See Section 12 of {contract_url} for the full process. "
            f"Town Notary base URL: {NOTARY_BASE}"
        ),
    }


@app.get("/contracts/{contract_id}/status")
def contract_status(contract_id: str):
    if contract_id not in _contracts:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
    c = _contracts[contract_id]
    return {
        "contract_id": contract_id,
        "status": c["status"],
        "notary_countersigned": bool(c.get("notary_signature_id")),
        "notary_signature_id": c.get("notary_signature_id", ""),
        "contract_url": f"{SELF_BASE}/contracts/{contract_id}.md",
    }


@app.post("/contracts/{contract_id}/accept")
def accept_contract(contract_id: str, req: AcceptRequest):
    if contract_id not in _contracts:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
    contract = _contracts[contract_id]
    contract["client_action"] = req.action
    contract["client_timestamp"] = datetime.utcnow().isoformat() + "Z"
    contract["client_acceptance_date"] = date.today().isoformat()
    if req.accepting_agent:
        contract["client_agent"] = req.accepting_agent
    if req.accepting_human:
        contract["client_human"] = req.accepting_human
    if contract["status"] == "executed":
        contract["status"] = "executed"
    else:
        contract["status"] = "accepted"
    return {
        "contract_id": contract_id,
        "status": contract["status"],
        "client_action": req.action,
        "contract_url": f"{SELF_BASE}/contracts/{contract_id}.md",
    }


# ── Skill and reference doc endpoints ────────────────────────────────────────

_SKILLS_DIR = Path(__file__).parent.parent / "skills" / "hackathon-contract-agent"

REFERENCE_FILES = {
    "contract-template": "reference/contract-template.md",
    "pricing-guide": "reference/pricing-guide.md",
    "notary-integration": "reference/notary-integration.md",
    "submission-guidelines": "reference/submission-guidelines.md",
}


@app.get("/skill.md", response_class=PlainTextResponse)
def serve_skill_md():
    p = _SKILLS_DIR / "SKILL.md"
    if p.exists():
        return p.read_text()
    raise HTTPException(status_code=404, detail="SKILL.md not found")


@app.get("/skills", response_class=PlainTextResponse)
def list_skills():
    """Return the SKILL.md — same as /skill.md, canonical discovery endpoint."""
    p = _SKILLS_DIR / "SKILL.md"
    if p.exists():
        return p.read_text()
    raise HTTPException(status_code=404, detail="SKILL.md not found")


@app.get("/reference", response_class=PlainTextResponse)
def list_reference():
    lines = ["# Reference Documents\n"]
    for name, path in REFERENCE_FILES.items():
        lines.append(f"- [{name}]({SELF_BASE}/reference/{name})")
    return "\n".join(lines)


@app.get("/reference/{doc_name}", response_class=PlainTextResponse)
def serve_reference_doc(doc_name: str):
    if doc_name not in REFERENCE_FILES:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown doc '{doc_name}'. Available: {list(REFERENCE_FILES.keys())}",
        )
    p = _SKILLS_DIR / REFERENCE_FILES[doc_name]
    if p.exists():
        return p.read_text()
    raise HTTPException(status_code=404, detail=f"File not found: {p}")


@app.get("/agent.json")
def agent_card():
    """Machine-readable agent identity card for A2A discovery."""
    return {
        "name": "Hackathon Contract Agent",
        "version": "1.0.0",
        "did": _AGENT_ID,
        "base_url": SELF_BASE,
        "skill_url": f"{SELF_BASE}/skill.md",
        "description": "Generates, prices, and exposes A2A service contracts with token-premium pricing. Town Notary countersignature is handled by parties directly per Section 12 of each contract.",
        "endpoints": {
            "generate": f"POST {SELF_BASE}/contracts/generate",
            "get_contract": f"GET {SELF_BASE}/contracts/{{contract_id}}.md",
            "seal": f"POST {SELF_BASE}/contracts/{{contract_id}}/seal",
            "status": f"GET {SELF_BASE}/contracts/{{contract_id}}/status",
            "accept": f"POST {SELF_BASE}/contracts/{{contract_id}}/accept",
            "list": f"GET {SELF_BASE}/contracts",
            "skill": f"GET {SELF_BASE}/skill.md",
            "reference_list": f"GET {SELF_BASE}/reference",
            "reference_doc": f"GET {SELF_BASE}/reference/{{doc_name}}",
        },
        "notary": {
            "name": "The Town Notary",
            "url": NOTARY_BASE,
            "role": "Countersigns executed contracts. Parties contact the Notary directly per Section 12 of the contract.",
        },
        "tags": ["contracts", "a2a", "pricing", "tokens", "hackathon"],
    }
