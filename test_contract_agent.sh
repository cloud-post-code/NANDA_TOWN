#!/usr/bin/env bash
# test_contract_agent.sh
# End-to-end curl test suite for the contract agent + pricing scraper.
# Covers: generate → pricing lookup → notarize (external Town Notary) → accept → notary receipt.
#
# Usage:
#   ./test_contract_agent.sh                         # uses live Railway URLs
#   CONTRACT_BASE=http://localhost:8000 \
#   PRICING_BASE=http://localhost:8001 \
#   ./test_contract_agent.sh                         # uses local servers
#
# Prerequisites: curl, jq

set -uo pipefail

CONTRACT_BASE="${CONTRACT_BASE:-https://hackathon-contract-agent-production.up.railway.app}"
PRICING_BASE="${PRICING_BASE:-https://pricing-scraper-production.up.railway.app}"
NOTARY_BASE="https://town-notary-production.up.railway.app"
NOTARY_SAVE_DIR="${NOTARY_SAVE_DIR:-./notary-receipts}"

GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
RESET="\033[0m"

PASS=0
FAIL=0
WARN=0

pass() { echo -e "${GREEN}PASS${RESET}  $1"; ((PASS++)); }
fail() { echo -e "${RED}FAIL${RESET}  $1"; ((FAIL++)); }
warn() { echo -e "${YELLOW}WARN${RESET}  $1"; ((WARN++)); }
section() {
  echo -e "\n${YELLOW}──────────────────────────────────────────${RESET}"
  echo -e "${YELLOW}  $1${RESET}"
  echo -e "${YELLOW}──────────────────────────────────────────${RESET}"
}

mkdir -p "$NOTARY_SAVE_DIR"

# ─── 1. Health checks ────────────────────────────────────────────────────────

section "1. Health checks"

echo "→ GET $CONTRACT_BASE/"
body=$(curl -sf --max-time 10 "$CONTRACT_BASE/" 2>/dev/null || true)
if echo "$body" | jq -e '.service' >/dev/null 2>&1; then
  VER=$(echo "$body" | jq -r '.version // "?"')
  pass "Contract agent root: version=$VER"
else
  fail "Contract agent root: unexpected response → $body"
fi

echo "→ GET $PRICING_BASE/"
body=$(curl -sf --max-time 10 "$PRICING_BASE/" 2>/dev/null || true)
if echo "$body" | jq -e '.service' >/dev/null 2>&1; then
  pass "Pricing scraper root responds"
  PRICING_UP=1
else
  warn "Pricing scraper unreachable — USD tests will use fallback rates (run locally with PRICING_BASE=http://localhost:8001)"
  PRICING_UP=0
fi

# ─── 2. Pricing scraper — model catalog ──────────────────────────────────────

section "2. Pricing scraper — model catalog"

if [ "${PRICING_UP:-0}" -eq 1 ]; then
  echo "→ GET $PRICING_BASE/pricing/models"
  PRICING_BODY=$(curl -sf "$PRICING_BASE/pricing/models" 2>/dev/null || echo '{}')
  MODEL_COUNT=$(echo "$PRICING_BODY" | jq '[(.all_models // [] | length), (.families // [] | map(.models | length) | add // 0)] | max')
  if [ "${MODEL_COUNT:-0}" -gt 0 ]; then
    pass "Pricing catalog: $MODEL_COUNT models"
  else
    fail "Pricing catalog empty or malformed"
  fi

  echo "→ GET $PRICING_BASE/pricing/models?provider=anthropic"
  ANTH_BODY=$(curl -sf "$PRICING_BASE/pricing/models?provider=anthropic" 2>/dev/null || echo '{}')
  ANTH_COUNT=$(echo "$ANTH_BODY" | jq '.count // 0')
  if [ "${ANTH_COUNT:-0}" -gt 0 ]; then
    pass "Anthropic filter: $ANTH_COUNT models"
  else
    fail "Anthropic filter returned no models"
  fi

  echo "→ GET $PRICING_BASE/pricing/models/claude-sonnet-4-6"
  SINGLE=$(curl -sf "$PRICING_BASE/pricing/models/claude-sonnet-4-6" 2>/dev/null || echo '{}')
  if echo "$SINGLE" | jq -e '.model' >/dev/null 2>&1; then
    INP=$(echo "$SINGLE" | jq -r '.input_per_1k_usd // "?"')
    OUT=$(echo "$SINGLE" | jq -r '.output_per_1k_usd // "?"')
    pass "Single model lookup claude-sonnet-4-6: input=$INP out=$OUT"
  else
    fail "Single model lookup failed for claude-sonnet-4-6"
  fi

  echo "→ GET $PRICING_BASE/scrape/status"
  SCRAPE_STATUS=$(curl -sf "$PRICING_BASE/scrape/status" 2>/dev/null || echo '{}')
  if echo "$SCRAPE_STATUS" | jq -e '.model_count' >/dev/null 2>&1; then
    AS_OF=$(echo "$SCRAPE_STATUS" | jq -r '.as_of // "unknown"')
    pass "Scrape status OK — as_of=$AS_OF"
  else
    fail "Scrape status endpoint broken"
  fi
else
  echo -e "${YELLOW}SKIP${RESET}  Pricing scraper tests (service unreachable)"
fi

# ─── 3. Agent card and skill ──────────────────────────────────────────────────

section "3. Agent card and skill"

echo "→ GET $CONTRACT_BASE/agent.json"
AGENT_CARD=$(curl -sf "$CONTRACT_BASE/agent.json" 2>/dev/null || echo '{}')
if echo "$AGENT_CARD" | jq -e '.name' >/dev/null 2>&1; then
  pass "Agent card: name=$(echo "$AGENT_CARD" | jq -r '.name') version=$(echo "$AGENT_CARD" | jq -r '.version // "?"')"
else
  fail "Agent card endpoint broken"
fi

if echo "$AGENT_CARD" | jq -e '.pricing_scraper.url' >/dev/null 2>&1; then
  pass "Agent card has pricing_scraper block (role: $(echo "$AGENT_CARD" | jq -r '.pricing_scraper.role' | cut -c1-60)...)"
else
  warn "Agent card missing pricing_scraper block — deployment may need update"
fi

if echo "$AGENT_CARD" | jq -e '.notary.endpoints.countersign' >/dev/null 2>&1; then
  pass "Agent card has notary.endpoints.countersign"
else
  warn "Agent card missing notary.endpoints — deployment may need update"
fi

if echo "$AGENT_CARD" | jq -e '.endpoints.notarize' >/dev/null 2>&1; then
  pass "Agent card has /notarize endpoint listed"
else
  warn "Agent card missing endpoints.notarize — deployment may need update"
fi

echo "→ GET $CONTRACT_BASE/skill.md"
SKILL=$(curl -sf "$CONTRACT_BASE/skill.md" -H "Accept: text/plain" 2>/dev/null || echo "")
if [ "${#SKILL}" -gt 100 ]; then
  pass "skill.md returned (${#SKILL} chars)"
else
  fail "skill.md empty or missing"
fi

# ─── 4. Generate a contract ───────────────────────────────────────────────────

section "4. Generate contract"

GENERATE_PAYLOAD='{
  "service_name": "Test LLM Pricing Report",
  "provider_agent": "curl-test-agent/1.0",
  "provider_endpoint": "https://example.com/agent",
  "provider_human": "Test Provider",
  "provider_legal_name": "Test Provider LLC",
  "client_agent": "curl-test-client/1.0",
  "client_endpoint": "https://example.com/client",
  "client_human": "Test Client",
  "client_legal_name": "Test Client Inc",
  "package": "standard",
  "smart_goal": "By 2026-07-13, Provider will deliver a pricing report so that Client has current LLM cost data.",
  "in_scope": ["Anthropic pricing analysis", "OpenAI pricing comparison", "Final markdown report"],
  "out_of_scope": ["Implementation of new pricing models"],
  "deliverables": [
    {
      "name": "pricing-report.md",
      "format": "Markdown",
      "due_date": "2026-07-13",
      "acceptance_criteria": "Report covers Anthropic, OpenAI, Google with per-1k-token USD rates",
      "revisions_included": 2
    }
  ],
  "model": "claude-sonnet-4-6",
  "token_estimate": 10000,
  "skill_premium_tokens": 2000,
  "skill_premium_justification": "Pricing scraper skill automates data collection saving ~50k tokens of manual research",
  "upcharge_pct": 0.12,
  "materials_estimate": 500,
  "currency": "tokens",
  "ip_model": "client_ownership",
  "human_review_required": true,
  "governing_jurisdiction": "California, USA"
}'

echo "→ POST $CONTRACT_BASE/contracts/generate"
GEN_RESP=$(curl -sf -X POST "$CONTRACT_BASE/contracts/generate" \
  -H "Content-Type: application/json" \
  -d "$GENERATE_PAYLOAD" 2>/dev/null || echo '{}')

if echo "$GEN_RESP" | jq -e '.contract_id' >/dev/null 2>&1; then
  CONTRACT_ID=$(echo "$GEN_RESP" | jq -r '.contract_id')
  CONTRACT_URL=$(echo "$GEN_RESP" | jq -r '.contract_url')
  pass "Contract generated: $CONTRACT_ID"
  echo "    contract_url = $CONTRACT_URL"
else
  fail "Contract generation failed → $GEN_RESP"
  echo -e "\n${RED}Cannot continue without a contract.${RESET}"
  exit 1
fi

# Verify generate response has token_fields (static) and usd_note (live)
if echo "$GEN_RESP" | jq -e '.token_fields.price_cap' >/dev/null 2>&1; then
  CAP=$(echo "$GEN_RESP" | jq -r '.token_fields.price_cap')
  TOTAL=$(echo "$GEN_RESP" | jq -r '.token_fields.total_tokens')
  pass "Generate response has static token_fields: price_cap=$CAP total_tokens=$TOTAL"
else
  warn "Generate response missing token_fields (older deployment?)"
fi

if echo "$GEN_RESP" | jq -e '.usd_note' >/dev/null 2>&1; then
  pass "Generate response has usd_note (USD computed at read time, not stored)"
else
  warn "Generate response missing usd_note (older deployment?)"
fi

# Verify next_step points to /notarize
NEXT_STEP=$(echo "$GEN_RESP" | jq -r '.next_step // ""')
if echo "$NEXT_STEP" | grep -q "notarize"; then
  pass "next_step points to /notarize: $NEXT_STEP"
else
  warn "next_step does not mention /notarize: $NEXT_STEP"
fi

# ─── 5. Fetch contract markdown — verify live USD + static tokens ─────────────

section "5. Fetch contract markdown (live USD pricing)"

echo "→ GET $CONTRACT_BASE/contracts/$CONTRACT_ID.md"
CONTRACT_MD=$(curl -sf "$CONTRACT_BASE/contracts/$CONTRACT_ID.md" 2>/dev/null || echo "")

if echo "$CONTRACT_MD" | grep -q "$CONTRACT_ID"; then
  pass "Contract markdown returned and contains contract_id"
else
  fail "Contract markdown missing or doesn't contain $CONTRACT_ID"
fi

if echo "$CONTRACT_MD" | grep -qi "token estimate\|price cap\|token_estimate"; then
  pass "Contract markdown has static token fields section"
else
  fail "Contract markdown missing token fields"
fi

if echo "$CONTRACT_MD" | grep -qi "live\|pricing scraper\|fetched"; then
  pass "Contract markdown indicates live USD pricing"
else
  warn "Contract markdown doesn't mention live pricing (may be older deployment)"
fi

if echo "$CONTRACT_MD" | grep -q '\$[0-9]'; then
  pass "Contract markdown contains USD cost values"
else
  fail "Contract markdown missing USD cost values"
fi

# ─── 6. Contract status ───────────────────────────────────────────────────────

section "6. Contract status"

echo "→ GET $CONTRACT_BASE/contracts/$CONTRACT_ID/status"
STATUS_RESP=$(curl -sf "$CONTRACT_BASE/contracts/$CONTRACT_ID/status" 2>/dev/null || echo '{}')
if echo "$STATUS_RESP" | jq -e '.status' >/dev/null 2>&1; then
  STATUS_VAL=$(echo "$STATUS_RESP" | jq -r '.status')
  pass "Status endpoint: status=$STATUS_VAL"
else
  fail "Status endpoint broken"
fi

# ─── 7. Notarize — external Town Notary ───────────────────────────────────────

section "7. Notarize via external Town Notary"

echo "→ POST $CONTRACT_BASE/contracts/$CONTRACT_ID/notarize"
NOTARIZE_RESP=$(curl -sf -X POST "$CONTRACT_BASE/contracts/$CONTRACT_ID/notarize" 2>/dev/null \
  || echo '{"notary_status":"failed","error":"endpoint_not_found"}')

NOTARY_RECEIPT_PATH="$NOTARY_SAVE_DIR/${CONTRACT_ID}-notarize.json"
echo "$NOTARIZE_RESP" > "$NOTARY_RECEIPT_PATH"

if echo "$NOTARIZE_RESP" | jq -e '.status' >/dev/null 2>&1; then
  N_STATUS=$(echo "$NOTARIZE_RESP" | jq -r '.status')
  if [ "$N_STATUS" = "executed" ]; then
    SIG=$(echo "$NOTARIZE_RESP" | jq -r '.notary_signature_id // "?"')
    DID=$(echo "$NOTARIZE_RESP" | jq -r '.notary_did_key // "?"')
    pass "Notarize: status=executed  signature_id=$SIG"
    echo "    notary_did_key = $DID"
    echo "    receipt saved → $NOTARY_RECEIPT_PATH"
  else
    N_ERR=$(echo "$NOTARIZE_RESP" | jq -r '.error // .notary_status // "?"')
    warn "Notarize returned status=$N_STATUS (notary may have refused badge — error: $N_ERR)"
    echo "    receipt saved → $NOTARY_RECEIPT_PATH"
  fi
else
  warn "Notarize endpoint not found or returned non-JSON — check deployment"
  echo "    raw saved → $NOTARY_RECEIPT_PATH"
fi

# ─── 8. Verify via Town Notary inspect ───────────────────────────────────────

section "8. Town Notary inspect (external service)"

echo "→ GET $NOTARY_BASE/inspect?runtime=$CONTRACT_ID"
INSPECT=$(curl -sf "$NOTARY_BASE/inspect?runtime=$CONTRACT_ID" 2>/dev/null \
  || echo '{"detail":"notary_unreachable"}')

INSPECT_PATH="$NOTARY_SAVE_DIR/${CONTRACT_ID}-inspect.json"
echo "$INSPECT" > "$INSPECT_PATH"

if echo "$INSPECT" | jq -e '.certified' >/dev/null 2>&1; then
  CERTIFIED=$(echo "$INSPECT" | jq -r '.certified')
  pass "Notary inspect: certified=$CERTIFIED"
  echo "    saved → $INSPECT_PATH"
elif echo "$INSPECT" | jq -e '.detail' >/dev/null 2>&1; then
  DETAIL=$(echo "$INSPECT" | jq -r '.detail')
  warn "Notary inspect: $DETAIL (not yet registered — badge format may not meet notary's admission gates)"
  echo "    saved → $INSPECT_PATH"
else
  warn "Notary inspect returned unexpected response"
  echo "    saved → $INSPECT_PATH"
fi

# ─── 9. Accept the contract ───────────────────────────────────────────────────

section "9. Accept contract"

ACCEPT_PAYLOAD='{"accepting_agent":"curl-test-client/1.0","accepting_human":"Test Client","action":"accepted"}'

echo "→ POST $CONTRACT_BASE/contracts/$CONTRACT_ID/accept"
ACCEPT_RESP=$(curl -sf -X POST "$CONTRACT_BASE/contracts/$CONTRACT_ID/accept" \
  -H "Content-Type: application/json" \
  -d "$ACCEPT_PAYLOAD" 2>/dev/null || echo '{}')

if echo "$ACCEPT_RESP" | jq -e '.status' >/dev/null 2>&1; then
  pass "Accept: status=$(echo "$ACCEPT_RESP" | jq -r '.status')"
else
  fail "Accept endpoint broken → $ACCEPT_RESP"
fi

# ─── 10. List contracts ───────────────────────────────────────────────────────

section "10. List contracts"

echo "→ GET $CONTRACT_BASE/contracts"
LIST_RESP=$(curl -sf "$CONTRACT_BASE/contracts" 2>/dev/null || echo '{}')
if echo "$LIST_RESP" | jq -e '.count' >/dev/null 2>&1; then
  COUNT=$(echo "$LIST_RESP" | jq -r '.count')
  FOUND=$(echo "$LIST_RESP" | jq -r --arg id "$CONTRACT_ID" \
    '[.contracts[] | select(.contract_id == $id)] | length' 2>/dev/null || echo "0")
  if [ "${FOUND:-0}" -gt 0 ]; then
    pass "Contract list: $COUNT total, our contract is listed"
  else
    fail "Contract list ($COUNT total) does not include $CONTRACT_ID"
  fi
else
  fail "List contracts endpoint broken"
fi

# ─── 11. Reference docs ───────────────────────────────────────────────────────

section "11. Reference docs"

echo "→ GET $CONTRACT_BASE/reference"
REF_LIST=$(curl -sf "$CONTRACT_BASE/reference" -H "Accept: text/plain" 2>/dev/null || echo "")
if echo "$REF_LIST" | grep -q "pricing-guide"; then
  pass "Reference index includes pricing-guide"
else
  fail "Reference index missing pricing-guide"
fi

for doc in contract-template pricing-guide notary-integration pricing-scraper-integration; do
  http_code=$(curl -s -o /dev/null -w "%{http_code}" "$CONTRACT_BASE/reference/$doc" -H "Accept: text/plain" 2>/dev/null)
  if [ "$http_code" = "200" ]; then
    body=$(curl -sf "$CONTRACT_BASE/reference/$doc" -H "Accept: text/plain" 2>/dev/null || echo "")
    pass "Reference doc '$doc': ${#body} chars"
  elif [ "$http_code" = "404" ]; then
    warn "Reference doc '$doc' not deployed (404) — check Dockerfile COPY of skills/"
  else
    fail "Reference doc '$doc' returned HTTP $http_code"
  fi
done

# ─── Summary ──────────────────────────────────────────────────────────────────

section "Summary"
TOTAL=$((PASS + FAIL + WARN))
echo -e "${GREEN}PASS: $PASS${RESET}  ${RED}FAIL: $FAIL${RESET}  ${YELLOW}WARN: $WARN${RESET}  Total checks: $TOTAL"
echo ""
echo "Notary receipts saved to: $NOTARY_SAVE_DIR/"
ls -1 "$NOTARY_SAVE_DIR/" 2>/dev/null || true

if [ "$FAIL" -gt 0 ]; then
  exit 1
else
  exit 0
fi
