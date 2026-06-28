# Deploy to Railway

## Prerequisites

- Railway account (railway.app)
- Railway CLI: `npm install -g @railway/cli`
- Git repo with this folder pushed

## Steps

### 1. Login to Railway

```bash
railway login
```

### 2. Create a new project

```bash
cd /path/to/NANDA_TOWN_PROJECT/contract-agent/api
railway init
# Select "Create new project" → name it "hackathon-contract-agent"
```

### 3. Set environment variables

```bash
railway variables set SELF_BASE_URL=https://hackathon-contract-agent-production.up.railway.app
```

Note: After first deploy Railway gives you the actual domain. Run this step again with the real URL if it differs.

### 4. Deploy

```bash
railway up
```

Railway detects the `Dockerfile` and builds automatically. The service will be live at:
```
https://hackathon-contract-agent-production.up.railway.app
```

### 5. Verify it's running

```bash
curl https://hackathon-contract-agent-production.up.railway.app/
# Expected: {"service": "Hackathon Contract Agent", "version": "1.0.0", ...}

curl https://hackathon-contract-agent-production.up.railway.app/contracts
# Expected: {"count": 0, "contracts": []}

curl https://hackathon-contract-agent-production.up.railway.app/skill.md
# Expected: The SKILL.md content
```

### 6. Test a full contract flow

```bash
# Generate a contract
curl -X POST https://hackathon-contract-agent-production.up.railway.app/contracts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "Survey Answering Service",
    "provider_agent": "survey-bot/1.0",
    "provider_endpoint": "https://survey-bot.example.com",
    "provider_human": "Your Name",
    "client_agent": "test-client/1.0",
    "package": "standard",
    "smart_goal": "By 2026-07-12, Provider will answer 50 survey questions per day so that Client data reaches 95% completion.",
    "in_scope": ["Answer survey questions", "Return structured JSON responses"],
    "out_of_scope": ["Data analysis", "Report generation"],
    "deliverables": [
      {
        "name": "Survey Responses",
        "format": "JSON",
        "due_date": "2026-07-12",
        "acceptance_criteria": "50 questions answered with >80% confidence score",
        "revisions_included": 2
      }
    ],
    "token_estimate": 50000,
    "skill_premium_tokens": 10000,
    "skill_premium_justification": "Saves ~200k tokens of manual prompt engineering",
    "currency": "tokens",
    "ip_model": "client_ownership",
    "human_review_required": false,
    "questions": {
      "who_do_you_help": "Researchers collecting structured data",
      "what_do_you_deliver": "JSON survey responses",
      "what_are_you_accessing": "Survey question API",
      "are_there_deliverable_questions": "None",
      "standard_policy": "Nanda Town platform policy",
      "appropriation_policy": "Client owns all responses"
    }
  }'

# You get back: { "contract_id": "A2A-20260628-XXXXXX", ... }

# Read the contract
curl https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260628-XXXXXX.md

# Notarize it
curl -X POST https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260628-XXXXXX/notarize

# Verify with Town Notary
curl "https://town-notary-production.up.railway.app/inspect?runtime=A2A-20260628-XXXXXX"
```

### 7. Submit to Nanda Town registry

Follow `skills/hackathon-contract-agent/reference/submission-guidelines.md`.

Quick path:
```bash
curl -X POST https://nandatown.projectnanda.org/api/skills \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Hackathon Contract Agent",
    "author": "Your Name",
    "description": "Generates, prices, and notarizes A2A service contracts for hackathon service offerings using a token-premium pricing model.",
    "submission_type": "hosted_link",
    "hosted_link": "https://hackathon-contract-agent-production.up.railway.app/skill.md",
    "endpoints": [
      "POST https://hackathon-contract-agent-production.up.railway.app/contracts/generate",
      "GET https://hackathon-contract-agent-production.up.railway.app/contracts/{contract_id}.md",
      "POST https://hackathon-contract-agent-production.up.railway.app/contracts/{contract_id}/notarize",
      "GET https://hackathon-contract-agent-production.up.railway.app/contracts/{contract_id}/status",
      "POST https://hackathon-contract-agent-production.up.railway.app/contracts/{contract_id}/accept",
      "GET https://hackathon-contract-agent-production.up.railway.app/contracts"
    ],
    "tags": ["contracts", "a2a", "pricing", "notary", "tokens", "hackathon"]
  }'
```

## Troubleshooting

**Notary returns 503:** The Town Notary may be temporarily down. The `/notarize` endpoint returns a 503 with a retry message. Wait 60 seconds and try again.

**SELF_BASE_URL is wrong:** If your Railway domain differs from the expected URL, update the env var:
```bash
railway variables set SELF_BASE_URL=https://your-actual-domain.up.railway.app
railway up
```

**Contract not found after restart:** The current implementation uses in-memory storage. For production, wire up a Railway Postgres service and replace `_contracts` dict with a DB table.
