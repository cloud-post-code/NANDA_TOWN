# Submission Guidelines — Nanda Town Skills Registry

## Overview

Once your Railway endpoint is live, submit the SKILL.md to the Nanda Town registry at
`https://nandatown.projectnanda.org/skills`. This makes the Hackathon Contract Agent
discoverable by any agent browsing the registry.

---

## Before you submit

### 1. Endpoint is live and reachable

All URLs in the SKILL.md must be real and reachable. The registry health-checks them.

```bash
# Test each endpoint before submitting
curl https://hackathon-contract-agent-production.up.railway.app/contracts
curl -X POST https://hackathon-contract-agent-production.up.railway.app/contracts/generate \
  -H "Content-Type: application/json" \
  -d '{"service_name": "test"}'
```

If an endpoint returns anything other than an error about missing fields, it is "live."
The health check does not care about the response body — just that it responds.

### 2. SKILL.md is hosted at a public URL

Option A — Host the SKILL.md file directly from your Railway app:
```
GET https://hackathon-contract-agent-production.up.railway.app/skill.md
```
Serve it as `text/markdown` or `text/plain`.

Option B — Push SKILL.md to a public GitHub repo and use the raw URL:
```
https://raw.githubusercontent.com/your-org/hackathon-contract-agent/main/SKILL.md
```

Option C — Paste the file directly in the submission form.

### 3. Test with the registry API

Before submitting through the form, test with the API:
```bash
curl https://nandatown.projectnanda.org/api/skills
```
You should get a JSON list of submitted skills. Confirm the format matches what you will submit.

---

## Submission form fields

Go to `https://nandatown.projectnanda.org/skills` and fill in:

| Field | What to enter |
|---|---|
| **Skill name** | `Hackathon Contract Agent` |
| **Your name or team** | Your name / team name from the hackathon |
| **One line: what does it do?** | `Generates, prices, and notarizes A2A service contracts for hackathon service offerings using a token-premium pricing model.` |
| **How to submit** | Select "Hosted link" if you have a public URL, or "Paste the file" |
| **Hosted .md link** | `https://hackathon-contract-agent-production.up.railway.app/skill.md` |
| **Your endpoints** | One per line — see list below |
| **Tags** | `contracts, a2a, pricing, notary, tokens, hackathon` |

### Endpoint list (paste into the form)

```
POST https://hackathon-contract-agent-production.up.railway.app/contracts/generate
GET  https://hackathon-contract-agent-production.up.railway.app/contracts/{contract_id}.md
POST https://hackathon-contract-agent-production.up.railway.app/contracts/{contract_id}/notarize
GET  https://hackathon-contract-agent-production.up.railway.app/contracts/{contract_id}/status
POST https://hackathon-contract-agent-production.up.railway.app/contracts/{contract_id}/accept
GET  https://hackathon-contract-agent-production.up.railway.app/contracts
```

---

## Programmatic registration (alternative to the form)

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

---

## After submitting

1. The registry will show your skill under "Submitted so far" with a link-responded / couldn't-reach-link status.
2. Share the API record URL with your hackathon team: `https://nandatown.projectnanda.org/api/skills/{your-skill-id}`
3. Other agents discover it via `GET https://nandatown.projectnanda.org/api/skills` and fetch your SKILL.md to learn how to use it.

---

## Quality checklist before submitting

- [ ] `/contracts/generate` returns a contract_id and contract_url
- [ ] `/{contract_id}.md` returns a filled Markdown contract
- [ ] `/notarize` calls the Town Notary and returns a notary_signature_id
- [ ] `/contracts` returns a list of existing contracts
- [ ] SKILL.md is publicly accessible at a stable URL
- [ ] All endpoints respond (even with an error) within 5 seconds
- [ ] The skill name, description, and tags are accurate
