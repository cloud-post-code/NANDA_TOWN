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

app = FastAPI(title="Hackathon Contract Agent", version="1.0.0")

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
    token_estimate: int
    skill_premium_tokens: int
    skill_premium_justification: str = "Saves manual prompt engineering effort"
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

MODEL_RATE = 0.000003  # $0.000003 per token (approximate mid-tier rate)

def _compute_tiers(token_est: int, skill_premium: int, materials: int):
    tiers = {
        "starter": {
            "token_est": int(token_est * 0.6),
            "cap": int(token_est * 0.6 * 1.2),
            "skill_premium": int(skill_premium * 0.5),
            "revisions": 1,
            "deliverables": "Core deliverable only",
        },
        "standard": {
            "token_est": token_est,
            "cap": int(token_est * 1.2),
            "skill_premium": skill_premium,
            "revisions": 3,
            "deliverables": "Core + follow-up refinements",
        },
        "premium": {
            "token_est": int(token_est * 1.5),
            "cap": int(token_est * 1.5 * 1.2),
            "skill_premium": int(skill_premium * 1.5),
            "revisions": 5,
            "deliverables": "Full scope + priority turnaround",
        },
    }
    for t in tiers.values():
        t["total"] = t["token_est"] + t["skill_premium"] + materials
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

The total price uses three layers: raw token/compute usage, materials, and a skill premium.

**Skill premium justification:** {r['skill_premium_justification']}

### Price components

| Component | Basis | Estimated amount | Cap |
|---|---|---:|---|
| Token / platform usage | Model + API compute | `{selected_tier['token_est']:,} tokens` | `{selected_tier['cap']:,} tokens` |
| Materials / third-party | Licenses, APIs, infra | `{r['materials_estimate']:,} tokens` | Pre-approval required >500 tokens |
| Skill premium | Capability above raw tokens | `{selected_tier['skill_premium']:,} tokens` | Fixed at signing |
| **Total** | | **`{selected_tier['total']:,} {r['currency']}`** | **Not to exceed `{selected_tier['cap'] + selected_tier['skill_premium'] + r['materials_estimate']:,}` without approval** |

### Payment terms

- **Currency:** `{r['currency']}`
- **Deposit:** 25% of total on signing (non-refundable once work begins)
- **Remaining:** On delivery of final accepted deliverable
- **Payment deadline:** Net 3 calendar days after acceptance

---

## 5. Offer Menu

| Option | Result | Token estimate | Price cap | Revisions |
|---|---|---:|---:|---:|
| A — Starter | Core deliverable only | `{tiers['starter']['token_est']:,}` | `{tiers['starter']['total']:,}` | 1 |
| B — Standard | Core + refinements | `{tiers['standard']['token_est']:,}` | `{tiers['standard']['total']:,}` | 3 |
| C — Premium | Full scope + priority | `{tiers['premium']['token_est']:,}` | `{tiers['premium']['total']:,}` | 5 |

- **Selected:** `{r['package'].title()}`
- **Negotiable:** Token estimate, timeline, revision count
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

    tiers = _compute_tiers(req.token_estimate, req.skill_premium_tokens, req.materials_estimate)

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
