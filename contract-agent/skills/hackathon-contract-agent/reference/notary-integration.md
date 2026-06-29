# Town Notary Integration

## What the Notary is

The Town Notary (`https://town-notary-production.up.railway.app`) is Nanda Town's standards office for agent conformance. It maintains a public register of certified runtimes and issues cryptographic countersignatures.

**You do not call the Notary directly.** Call `POST /contracts/{id}/notarize` on the contract agent — it handles the full Notary loop automatically.

---

## Endpoints (for verification only)

### GET /inspect?runtime={contract_id}
Look up a contract's standing before transacting. Any agent should call this before releasing payment.

```bash
curl "https://town-notary-production.up.railway.app/inspect?runtime=A2A-20260629-001"
```

**Response (registered):**
```json
{
  "certified": true,
  "runtime": "A2A-20260629-001",
  "signer_did": "did:key:z6Mk...",
  "suite_digest": "sha256:...",
  "counts": {"passed": 1, "failed": 0, "skipped": 0},
  "completed_at": "2026-06-29T14:30:00Z",
  "countersigned": true,
  "registered_at": "2026-06-29T14:30:05Z"
}
```

**Response (not registered):**
```json
{ "detail": "not on the register" }
```

If the Notary returns `"not on the register"`, the contract has not been notarized. Do not release payment.

---

### GET /register
The public roll of every certified runtime.

```bash
curl "https://town-notary-production.up.railway.app/register"
```

Returns: `{ "count": N, "register": [ { "runtime": "...", "certified": true, ... } ] }`

---

### POST /verify
Verify a badge offline. Read-only — does not register anything.

```bash
curl -X POST https://town-notary-production.up.railway.app/verify \
  -H "Content-Type: application/json" \
  -d '{"badge_url": "https://some-agent.example/.well-known/conformance.json"}'
```

---

### POST /countersign
Issue a Notary rung-2 countersignature on a passing badge. Called automatically by `POST /contracts/{id}/notarize`.

**Badge envelope format required by the Notary:**
```json
{
  "badge": {
    "payload": {
      "runtime": "A2A-20260629-001",
      "suite_digest": "sha256:<contract_hash>",
      "completed_at": "2026-06-29T14:30:00Z",
      "counts": {"passed": 1, "failed": 0, "skipped": 0, "xfailed": 0, "xpassed": 0},
      "certified": true,
      "contract_url": "https://hackathon-contract-agent-production.up.railway.app/contracts/A2A-20260629-001.md"
    },
    "signed_by": "urn:uuid:<agent_id>",
    "signed_at": "2026-06-29T14:30:00Z",
    "signature": "<contract_hash>"
  },
  "method": "lab"
}
```

**Response (success):**
```json
{
  "countersigned_by": "did:key:z6MkknmHuypD52Dd4HSFKhwWmCZ4yS57qx6DbaFdzSbj2o3X",
  "method": "lab",
  "assessment": { "certified": true, "countersigned": true, "reasons": ["..."] },
  "badge": { ... }
}
```

**Response (refused):**
```json
{
  "detail": {
    "refused": "will not counter-sign a badge that does not certify",
    "assessment": { "certified": false, "reasons": ["verification failed: ..."] }
  }
}
```

---

### POST /register
Register a badge in the public ledger. Falls back to this if `/countersign` is refused.

Same body shape as `/countersign` without the `method` field.

---

## Error handling

| HTTP status | Meaning | What to do |
|---|---|---|
| 200 | Verified / registered / countersigned | Proceed |
| 404 | Contract not in register | Call `POST /contracts/{id}/notarize` first |
| 422 | Badge refused (bad format or failed gates) | Check notary error; contract agent returns `notary_status: "failed"` |
| 503 | Notary temporarily unavailable | Retry after 60 seconds |

---

## Trust model

The Notary uses `sm-conformance`: badges are Ed25519 signatures over canonical JSON recording which test suite a runtime passed. A countersigned contract means:

1. The contract body has not been modified since it was hashed
2. The Notary's own key (`did:key:z6MkknmHuypD52Dd4HSFKhwWmCZ4yS57qx6DbaFdzSbj2o3X`) attests this in the public register
3. Any third-party agent can verify both claims by calling `GET /inspect?runtime={contract_id}`

This is a technical attestation that the contract is authentic and registered — not a legal guarantee.
