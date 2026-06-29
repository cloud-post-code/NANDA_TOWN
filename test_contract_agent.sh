#!/usr/bin/env bash
# test_contract_agent.sh
# End-to-end curl test suite for the contract agent + pricing scraper.
# Covers: generate → pricing lookup → accept → notarize (save notary).
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

pass() { echo -e "${GREEN}PASS${RESET}  $1"; ((PASS++)); }
fail() { echo -e "${RED}FAIL${RESET}  $1"; ((FAIL++)); }
section() { echo -e "\n${YELLOW}──────────────────────────────────────────${RESET}"; echo -e "${YELLOW}  $1${RESET}"; echo -e "${YELLOW}──────────────────────────────────────────${RESET}"; }

mkdir -p "$NOTARY_SAVE_DIR"

# ─── 1. Health checks ────────────────────────────────────────────────────────

section "1. Health checks"

echo "→ GET $CONTRACT_BASE/"
body=$(curl -sf "$CONTRACT_BASE/" || true)
if echo "$body" | jq -e '.service' >/dev/null 2>&1; then
  pass "Contract agent root responds"
else
  fail "Contract agent root: unexpected response → $body"
fi

echo "→ GET $PRICING_BASE/"
body=$(curl -sf --max-time 10 "$PRICING_BASE/" 2>/dev/null || true)
if echo "$body" | jq -e '.service' >/dev/null 2>&1; then
  pass "Pricing scraper root responds"
  PRICING_UP=1
else
  echo -e "${YELLOW}WARN${RESET}  Pricing scraper unreachable — skipping scraper tests (run locally with PRICING_BASE=http://localhost:8001)"
  PRICING_UP=0
fi

# ─── 2. Pricing scraper — model catalog ──────────────────────────────────────

section "2. Pricing scraper — model catalog"

if [ "${PRICING_UP:-0}" -eq 1 ]; then
  echo "→ GET $PRICING_BASE/pricing/models"
  PRICING_BODY=$(curl -sf "$PRICING_BASE/pricing/models")
  MODEL_COUNT=$(echo "$PRICING_BODY" | jq '[(.all_models // [] | length), (.families // [] | map(.models | length) | add // 0)] | max')
  if [ "${MODEL_COUNT:-0}" -gt 0 ]; then
    pass "Pricing catalog has $MODEL_COUNT models"
  else
    fail "Pricing catalog empty or malformed"
  fi

  echo "→ GET $PRICING_BASE/pricing/models?provider=anthropic"
  ANTH_BODY=$(curl -sf "$PRICING_BASE/pricing/models?provider=anthropic")
  ANTH_COUNT=$(echo "$ANTH_BODY" | jq '.count // 0')
  if [ "${ANTH_COUNT:-0}" -gt 0 ]; then
    pass "Anthropic filter returns $ANTH_COUNT models"
  else
    fail "Anthropic filter returned no models"
  fi

  echo "→ GET $PRICING_BASE/pricing/models/claude-sonnet-4-6"
  SINGLE=$(curl -sf "$PRICING_BASE/pricing/models/claude-sonnet-4-6" || echo '{}')
  if echo "$SINGLE" | jq -e '.model' >/dev/null 2>&1; then
    RATE=$(echo "$SINGLE" | jq -r '.input_per_1k_usd // "?"')
    pass "Single model lookup: claude-sonnet-4-6  input_per_1k_usd=$RATE"
  else
    fail "Single model lookup failed for claude-sonnet-4-6"
  fi

  echo "→ GET $PRICING_BASE/scrape/status"
  SCRAPE_STATUS=$(curl -sf "$PRICING_BASE/scrape/status")
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
AGENT_CARD=$(curl -sf "$CONTRACT_BASE/agent.json")
if echo "$AGENT_CARD" | jq -e '.name' >/dev/null 2>&1; then
  pass "Agent card responds with name=$(echo "$AGENT_CARD" | jq -r '.name')"
else
  fail "Agent card endpoint broken"
fi
# pricing_scraper block present only in v1.1+ deployment
if echo "$AGENT_CARD" | jq -e '.pricing_scraper.url' >/dev/null 2>&1; then
  SCRAPER_URL=$(echo "$AGENT_CARD" | jq -r '.pricing_scraper.url')
  pass "Agent card has pricing_scraper.url = $SCRAPER_URL"
else
  echo -e "${YELLOW}WARN${RESET}  Agent card missing pricing_scraper block (older deployment — needs redeploy)"
fi

echo "→ GET $CONTRACT_BASE/skill.md"
SKILL=$(curl -sf "$CONTRACT_BASE/skill.md" -H "Accept: text/plain")
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
  "smart_goal": "Deliver a pricing analysis report for all major LLM providers within 14 days.",
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
  "skill_premium_justification": "Pricing scraper skill automates data collection",
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
  -d "$GENERATE_PAYLOAD")

if echo "$GEN_RESP" | jq -e '.contract_id' >/dev/null 2>&1; then
  CONTRACT_ID=$(echo "$GEN_RESP" | jq -r '.contract_id')
  CONTRACT_URL=$(echo "$GEN_RESP" | jq -r '.contract_url')
  pass "Contract generated: $CONTRACT_ID"
  echo "    contract_url = $CONTRACT_URL"
else
  fail "Contract generation failed → $GEN_RESP"
  echo -e "\n${RED}Cannot continue without a contract. Exiting.${RESET}"
  exit 1
fi

# ─── 5. Fetch contract markdown ───────────────────────────────────────────────

section "5. Fetch contract markdown"

echo "→ GET $CONTRACT_BASE/contracts/$CONTRACT_ID.md"
CONTRACT_MD=$(curl -sf "$CONTRACT_BASE/contracts/$CONTRACT_ID.md")
if echo "$CONTRACT_MD" | grep -q "$CONTRACT_ID"; then
  pass "Contract markdown returned and contains contract_id"
else
  fail "Contract markdown missing or doesn't contain $CONTRACT_ID"
fi

if echo "$CONTRACT_MD" | grep -qi "pricing\|token\|price"; then
  pass "Contract markdown contains pricing section"
else
  fail "Contract markdown missing pricing section"
fi

# ─── 6. Contract status ───────────────────────────────────────────────────────

section "6. Contract status"

echo "→ GET $CONTRACT_BASE/contracts/$CONTRACT_ID/status"
STATUS_RESP=$(curl -sf "$CONTRACT_BASE/contracts/$CONTRACT_ID/status")
if echo "$STATUS_RESP" | jq -e '.status' >/dev/null 2>&1; then
  STATUS_VAL=$(echo "$STATUS_RESP" | jq -r '.status')
  pass "Status endpoint: status=$STATUS_VAL"
else
  fail "Status endpoint broken"
fi

# ─── 7. Seal the contract ─────────────────────────────────────────────────────

section "7. Seal contract"

echo "→ POST $CONTRACT_BASE/contracts/$CONTRACT_ID/seal"
SEAL_RESP=$(curl -sf -X POST "$CONTRACT_BASE/contracts/$CONTRACT_ID/seal")
if echo "$SEAL_RESP" | jq -e '.status' >/dev/null 2>&1; then
  SEALED_STATUS=$(echo "$SEAL_RESP" | jq -r '.status')
  pass "Seal response: status=$SEALED_STATUS"
else
  fail "Seal endpoint broken → $SEAL_RESP"
fi

# ─── 8. Accept the contract ───────────────────────────────────────────────────

section "8. Accept contract"

ACCEPT_PAYLOAD='{
  "accepting_agent": "curl-test-client/1.0",
  "accepting_human": "Test Client",
  "action": "accepted"
}'

echo "→ POST $CONTRACT_BASE/contracts/$CONTRACT_ID/accept"
ACCEPT_RESP=$(curl -sf -X POST "$CONTRACT_BASE/contracts/$CONTRACT_ID/accept" \
  -H "Content-Type: application/json" \
  -d "$ACCEPT_PAYLOAD")

if echo "$ACCEPT_RESP" | jq -e '.status' >/dev/null 2>&1; then
  ACCEPT_STATUS=$(echo "$ACCEPT_RESP" | jq -r '.status')
  pass "Accept response: status=$ACCEPT_STATUS"
else
  fail "Accept endpoint broken → $ACCEPT_RESP"
fi

# ─── 9. Notarize — countersign and save receipt ───────────────────────────────

section "9. Notarize and save notary receipt"

echo "→ POST $NOTARY_BASE/countersign  (contract_url=$CONTRACT_URL)"
NOTARY_RESP=$(curl -sf -X POST "$NOTARY_BASE/countersign" \
  -H "Content-Type: application/json" \
  -d "{\"badge_url\": \"$CONTRACT_URL\", \"method\": \"url\"}" \
  || echo '{"error":"notary_unreachable"}')

NOTARY_RECEIPT_PATH="$NOTARY_SAVE_DIR/${CONTRACT_ID}-notary.json"
echo "$NOTARY_RESP" > "$NOTARY_RECEIPT_PATH"

if echo "$NOTARY_RESP" | jq -e '.signature_id' >/dev/null 2>&1; then
  SIG_ID=$(echo "$NOTARY_RESP" | jq -r '.signature_id')
  NOTARY_TS=$(echo "$NOTARY_RESP" | jq -r '.timestamp // "unknown"')
  NOTARY_KEY=$(echo "$NOTARY_RESP" | jq -r '.notary_did_key // "unknown"')
  pass "Notary countersigned: signature_id=$SIG_ID"
  echo "    timestamp    = $NOTARY_TS"
  echo "    notary_key   = $NOTARY_KEY"
  echo "    receipt saved → $NOTARY_RECEIPT_PATH"
else
  # Notary might not be available in all test environments — warn, don't hard-fail
  echo -e "${YELLOW}WARN${RESET}  Notary countersign unavailable (network/service may be down)"
  echo "    raw response saved → $NOTARY_RECEIPT_PATH"
fi

echo "→ GET $NOTARY_BASE/inspect?runtime=$CONTRACT_ID"
INSPECT=$(curl -sf "$NOTARY_BASE/inspect?runtime=$CONTRACT_ID" \
  || echo '{"registered":false,"error":"notary_unreachable"}')

INSPECT_PATH="$NOTARY_SAVE_DIR/${CONTRACT_ID}-inspect.json"
echo "$INSPECT" > "$INSPECT_PATH"

if echo "$INSPECT" | jq -e '.registered' >/dev/null 2>&1; then
  REGISTERED=$(echo "$INSPECT" | jq -r '.registered')
  pass "Notary inspect returned: registered=$REGISTERED"
  echo "    inspect saved → $INSPECT_PATH"
else
  echo -e "${YELLOW}WARN${RESET}  Notary inspect unavailable"
  echo "    raw response saved → $INSPECT_PATH"
fi

# ─── 10. List contracts ───────────────────────────────────────────────────────

section "10. List contracts"

echo "→ GET $CONTRACT_BASE/contracts"
LIST_RESP=$(curl -sf "$CONTRACT_BASE/contracts")
if echo "$LIST_RESP" | jq -e '.count' >/dev/null 2>&1; then
  COUNT=$(echo "$LIST_RESP" | jq -r '.count')
  FOUND=$(echo "$LIST_RESP" | jq -r --arg id "$CONTRACT_ID" \
    '.contracts[] | select(.contract_id == $id) | .contract_id' || true)
  if [ "$FOUND" = "$CONTRACT_ID" ]; then
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
REF_LIST=$(curl -sf "$CONTRACT_BASE/reference" -H "Accept: text/plain")
if echo "$REF_LIST" | grep -q "pricing-guide"; then
  pass "Reference index includes pricing-guide"
else
  fail "Reference index missing pricing-guide"
fi

for doc in contract-template pricing-guide notary-integration pricing-scraper-integration; do
  http_code=$(curl -s -o /dev/null -w "%{http_code}" "$CONTRACT_BASE/reference/$doc" -H "Accept: text/plain" 2>/dev/null)
  if [ "$http_code" = "200" ]; then
    body=$(curl -sf "$CONTRACT_BASE/reference/$doc" -H "Accept: text/plain" 2>/dev/null || true)
    pass "Reference doc '$doc' returned (${#body} chars)"
  elif [ "$http_code" = "404" ]; then
    echo -e "${YELLOW}WARN${RESET}  Reference doc '$doc' not deployed (404) — file not bundled in Docker image"
  else
    fail "Reference doc '$doc' returned HTTP $http_code"
  fi
done

# ─── Summary ──────────────────────────────────────────────────────────────────

section "Summary"
TOTAL=$((PASS + FAIL))
echo -e "${GREEN}PASS: $PASS${RESET}  ${RED}FAIL: $FAIL${RESET}  Total: $TOTAL"
echo ""
echo "Notary receipts saved to: $NOTARY_SAVE_DIR/"
ls -1 "$NOTARY_SAVE_DIR/" 2>/dev/null || true

if [ "$FAIL" -gt 0 ]; then
  exit 1
else
  exit 0
fi
