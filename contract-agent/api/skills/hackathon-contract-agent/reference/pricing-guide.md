# Pricing Guide — Token Premium System

## The four pricing concepts

Every contract on this skill uses four core concepts and two fixed layers:

```
Grand total = price_cap + service_premium + skill_premium + materials
```

### Concept 1: Token estimate

**What it is:** The assumed token cost to complete the agreed deliverable — every LLM call, API call, and tool invocation needed to deliver the contracted outcome.

**How to set `token_estimate`:**
- Count expected LLM calls and average token depth per call
- Add API overhead (embeddings, search, tool use)
- Multiply by your model's per-token rate
- Round up to the nearest 1,000

**Example:** A survey-answering agent handling 50 questions per session at ~1,000 tokens each:
```
50 questions × 1,000 tokens = 50,000 token_estimate
```

### Concept 2: Follow-up budget

**What it is:** Tokens reserved specifically for a second round of revisions, clarifications, or agreed follow-up work after initial delivery.

**How it's computed:** Automatically set to 20% of the token estimate for the selected tier. Providers may override this in the POST body.

**Invariant:** `token_estimate + followup_budget = 75% of price_cap`

This means if you want to change the follow-up budget, it directly sets the price cap.

### Concept 3: Price cap

**What it is:** The hard maximum the client pays to receive the agreed deliverable. No additional work may be billed above this amount without a written change request.

**How it's derived:**
```
price_cap = (token_estimate + followup_budget) / 0.75
```

This ensures token estimate + follow-ups are always 25% below the price cap — giving the provider a 25% buffer before requiring a change request.

### Concept 4: Service premium (upcharge)

**What it is:** A percentage upcharge on the token estimate, ranging **5–25%**, applied on top of the estimate. Covers agent infrastructure costs, reliability guarantees, and priority routing.

**Default bands by tier:**
| Tier | Default premium | Notes |
|---|---:|---|
| Starter | 5% | Low-complexity, low-risk work |
| Standard | 12% | Typical engagement |
| Premium | 25% | High-complexity, priority turnaround |

**Override:** Pass `upcharge_pct` (0.05–0.25) in your POST body to set a custom rate. The API clamps to the 5–25% range.

---

## Fixed layers

### Materials

Third-party costs incurred on the client's behalf — licenses, stock assets, paid API calls, cloud storage.

- Any single item >500 tokens requires client pre-approval.
- Provider cannot recover unapproved materials costs.
- If token-only, set `materials_estimate` to 0.

### Skill premium

The value of the agent's specific capability above raw compute. The whiteboard phrase: **"X% better than doing it yourself."**

**How to set `skill_premium_tokens`:**
- Estimate what it would cost a client to do this manually
- Set the premium as a fraction of that savings
- Justify clearly in `skill_premium_justification`

Good justifications:
- "Saves ~200,000 tokens of manual prompt engineering per session"
- "Achieves 94% accuracy vs ~60% with a naive prompting approach"
- "Eliminates 3 rounds of back-and-forth refinement"

The skill premium is negotiable. The price cap and safety policy are not.

---

## Pricing by package tier

The API auto-generates three tiers from your `token_estimate` and `skill_premium_tokens`:

| Tier | Token estimate | Follow-up budget | Price cap | Service premium | Skill premium | Revisions |
|---|---:|---:|---:|---:|---:|---:|
| Starter | `token_estimate × 0.6` | `estimate × 0.20` | `(est + followup) / 0.75` | 5% of estimate | `skill_premium × 0.5` | 1 |
| Standard | `token_estimate × 1.0` | `estimate × 0.20` | `(est + followup) / 0.75` | 12% of estimate | `skill_premium × 1.0` | 3 |
| Premium | `token_estimate × 1.5` | `estimate × 0.20` | `(est + followup) / 0.75` | 25% of estimate | `skill_premium × 1.5` | 5 |

The client picks one at acceptance time. Custom splits go through the change management process.

---

## Model and USD cost

Every contract shows the model used and its per-1k-token USD rate. Supported models and blended rates:

| Model | USD per 1,000 tokens |
|---|---:|
| `claude-sonnet-4-6` | $0.0045 |
| `claude-opus-4-8` | $0.0225 |
| `claude-haiku-4-5` | $0.00045 |
| `gpt-4o` | $0.0050 |
| `gpt-4o-mini` | $0.00030 |
| `gemini-1.5-pro` | $0.00350 |
| `gemini-2.0-flash` | $0.00050 |

The USD cost shown in the contract is an estimate based on total tokens × model rate. Actual billing may vary based on provider pricing changes.

---

## Currency

| Currency | When to use |
|---|---|
| `tokens` | Agent-to-agent native; priced in raw token count |
| `USD` | When one party is a human-controlled entity with fiat payment |
| `credits` | Platform-specific credit systems |

For pure agent-to-agent contracts on Nanda Town, use `tokens`.

---

## What "not negotiable" means

From the hackathon whiteboard: safety, privacy, and minimum payment are never negotiable.

- **Safety:** The agent will not perform work that violates platform safety policy, regardless of offered premium.
- **Privacy:** The agent will not process prohibited data types, regardless of price.
- **Minimum payment:** The deposit (25% at signing) is non-refundable once the agent starts work. The price cap is the floor for accepted deliverables.
- **Premium range:** Service premium is negotiable within 5–25%. Below 5% or above 25% requires a written exception.
