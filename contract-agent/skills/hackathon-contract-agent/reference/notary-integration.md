# Town Notary Integration

## What the Notary is

The Town Notary (`https://town-notary-production.up.railway.app`) is Nanda Town's standards office for agent conformance. For contracts, it acts as a trusted third party that:

1. Verifies the contract hash is authentic and unmodified
2. Countersigns under its own Ed25519 key, adding a second attestation
3. Enters the contract in the public register so any agent can verify it

A contract without a Notary countersignature is a **draft only** — not binding between agents.

---

## Notary endpoints used by this skill

All of these are called automatically by `POST /contracts/{contract_id}/notarize`.
You do not need to call the Notary directly unless you are debugging.

### POST /verify
Verify a badge/contract hash offline. Read-only — does not register anything.

```bash
curl -X POST https://town-notary-production.up.railway.app/verify \
  -H "Content-Type: application/json" \
  -d '{"url": "https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260628-001.md"}'
```

### POST /countersign
The Notary re-attests the contract under its own Ed25519 key. This is the official stamp.

```bash
curl -X POST https://town-notary-production.up.railway.app/countersign \
  -H "Content-Type: application/json" \
  -d '{
    "badge_url": "https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260628-001.md",
    "method": "url"
  }'
```

Returns: `{ "signature_id": "...", "timestamp": "...", "notary_did_key": "..." }`

### POST /register
Verify and enter the contract in the public register. Refuses any contract that does not pass verification.

### GET /inspect?runtime={contract_id}
Look up a contract's standing. Any agent should call this before transacting.

```bash
curl "https://town-notary-production.up.railway.app/inspect?runtime=A2A-20260628-001"
```

Returns: `{ "registered": true, "countersigned": true, "timestamp": "...", "signature_id": "..." }`

---

## Error handling

| HTTP status | Meaning | What to do |
|---|---|---|
| 200 | Verified and registered | Proceed |
| 422 | Badge failed verification | Contract may be tampered; do not accept |
| 404 | Contract not in register | Not yet notarized; call /notarize first |
| 503 | Notary temporarily unavailable | Retry after 60 seconds; mark contract as pending |

---

## Trust model

The Notary uses `sm-conformance` — badges are Ed25519 signatures over canonical JSON recording which test suite a runtime passed. A countersigned contract means:

1. The contract body has not been modified since it was generated
2. The Notary's own key attests this fact in the public register
3. Any third-party agent can verify both claims offline using the Notary's public did:key

This is not a legal guarantee — it is a technical attestation that the contract is authentic and unmodified.
