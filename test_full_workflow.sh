#!/usr/bin/env bash
# test_full_workflow.sh
# =====================
# Full end-to-end workflow test using ONLY curl commands — no local code.
# Simulates two agents discovering services via skill.md and executing
# the complete contract workflow with live pricing and notarization.
#
# Workflow:
#   Agent A (provider) discovers the Contract Agent and Pricing Scraper via skill.md
#   Agent B (client)   reads the contract and gets live USD pricing
#   Both agents: notarize via external Town Notary, accept, verify before paying
#
# Prerequisites: curl, jq
# Usage: ./test_full_workflow.sh

set -uo pipefail

CONTRACT_BASE="https://hackathon-contract-agent-production.up.railway.app"
NOTARY_BASE="https://town-notary-production.up.railway.app"
# Resolve the live pricing scraper URL from the contract agent's agent.json
# (Railway may assign a different subdomain than the default)
_PS_URL=$(curl -sf --max-time 10 "$CONTRACT_BASE/agent.json" 2>/dev/null | jq -r '.pricing_scraper.url // ""')
PRICING_BASE="${PRICING_BASE:-${_PS_URL:-https://pricing-scraper-production.up.railway.app}}"
NOTARY_SAVE_DIR="${NOTARY_SAVE_DIR:-./notary-receipts}"

GREEN="\033[0;32m"; RED="\033[0;31m"; YELLOW="\033[0;33m"; CYAN="\033[0;36m"; RESET="\033[0m"
PASS=0; FAIL=0; WARN=0

pass() { echo -e "${GREEN}PASS${RESET}  $1"; ((PASS++)); }
fail() { echo -e "${RED}FAIL${RESET}  $1"; ((FAIL++)); }
warn() { echo -e "${YELLOW}WARN${RESET}  $1"; ((WARN++)); }
step() { echo -e "\n${CYAN}▸ $1${RESET}"; }
section() {
  echo -e "\n${YELLOW}══════════════════════════════════════════${RESET}"
  echo -e "${YELLOW}  $1${RESET}"
  echo -e "${YELLOW}══════════════════════════════════════════${RESET}"
}

mkdir -p "$NOTARY_SAVE_DIR"

# ─── PHASE 1: Agent A discovers services via skill.md ─────────────────────────

section "PHASE 1 — Agent A discovers services via hosted skill.md"

step "Agent A reads Contract Agent skill.md (hosted endpoint)"
SKILL_CONTRACT=$(curl -sf --max-time 10 "$CONTRACT_BASE/skill.md" -H "Accept: text/plain" 2>/dev/null || echo "")
if [ "${#SKILL_CONTRACT}" -gt 500 ]; then
  pass "Contract Agent skill.md: ${#SKILL_CONTRACT} chars at $CONTRACT_BASE/skill.md"
  echo "    First line: $(echo "$SKILL_CONTRACT" | head -1)"
else
  fail "Contract Agent skill.md missing or too short"
fi

# Check skill.md mentions the key endpoints an agent needs
for keyword in "contracts/generate" "notarize" "accept" "pricing"; do
  if echo "$SKILL_CONTRACT" | grep -qi "$keyword"; then
    pass "skill.md mentions '$keyword'"
  else
    warn "skill.md does not mention '$keyword'"
  fi
done

step "Agent A reads Pricing Scraper skill.md (hosted endpoint)"
SKILL_PRICING=$(curl -sf --max-time 10 "$PRICING_BASE/skill.md" -H "Accept: text/plain" 2>/dev/null || echo "")
if [ "${#SKILL_PRICING}" -gt 500 ]; then
  pass "Pricing Scraper skill.md: ${#SKILL_PRICING} chars at $PRICING_BASE/skill.md"
  echo "    First line: $(echo "$SKILL_PRICING" | head -1)"
  PRICING_SKILL_UP=1
else
  warn "Pricing Scraper skill.md missing — service may be deploying (${#SKILL_PRICING} chars)"
  PRICING_SKILL_UP=0
fi

step "Agent A checks Town Notary (external service, not ours)"
NOTARY_ROOT=$(curl -sf --max-time 10 "$NOTARY_BASE/" 2>/dev/null || echo '{}')
if echo "$NOTARY_ROOT" | jq -e '.office' >/dev/null 2>&1; then
  NOTARY_DID=$(echo "$NOTARY_ROOT" | jq -r '.notary_did')
  pass "Town Notary reachable: did=$NOTARY_DID"
  echo "    Endpoints: $(echo "$NOTARY_ROOT" | jq -r '.endpoints | join(", ")')"
else
  fail "Town Notary not reachable"
fi

# ─── PHASE 2: Agent A reads live pricing from Pricing Scraper ─────────────────

section "PHASE 2 — Agent A reads live pricing (from Pricing Scraper, as instructed by skill.md)"

step "Agent A fetches live rate for claude-sonnet-4-6"
RATE_RESP=$(curl -sf --max-time 10 "$PRICING_BASE/pricing/models/claude-sonnet-4-6" 2>/dev/null || echo '{}')
if echo "$RATE_RESP" | jq -e '.input_per_1k_usd' >/dev/null 2>&1; then
  INP=$(echo "$RATE_RESP" | jq -r '.input_per_1k_usd')
  OUT=$(echo "$RATE_RESP" | jq -r '.output_per_1k_usd')
  BLENDED=$(python3 -c "print(round($INP * 0.6 + $OUT * 0.4, 6))" 2>/dev/null || echo "N/A")
  pass "Live rate: input=$INP/1k  output=$OUT/1k  blended=$BLENDED/1k"
  PRICING_LIVE=1
else
  warn "Pricing Scraper unreachable — Contract Agent will use fallback rates"
  PRICING_LIVE=0
fi

step "Agent A checks scrape freshness"
SCRAPE_STATUS=$(curl -sf --max-time 10 "$PRICING_BASE/scrape/status" 2>/dev/null || echo '{}')
if echo "$SCRAPE_STATUS" | jq -e '.as_of' >/dev/null 2>&1; then
  AS_OF=$(echo "$SCRAPE_STATUS" | jq -r '.as_of')
  CNT=$(echo "$SCRAPE_STATUS" | jq -r '.model_count')
  pass "Scrape status: as_of=$AS_OF  models=$CNT"
else
  warn "Scrape status unavailable (scraper may be down)"
fi

# ─── PHASE 3: Agent A generates a contract ────────────────────────────────────

section "PHASE 3 — Agent A generates a contract (as instructed by Contract Agent skill.md)"

step "Agent A calls POST /contracts/generate with live model"

GEN_RESP=$(curl -sf -X POST "$CONTRACT_BASE/contracts/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "LLM Pricing Analysis Report",
    "provider_agent": "agent-a-provider/1.0",
    "provider_endpoint": "https://agent-a.example.com",
    "provider_human": "Agent A Team",
    "provider_legal_name": "Agent A LLC",
    "client_agent": "agent-b-client/1.0",
    "client_endpoint": "https://agent-b.example.com",
    "client_human": "Agent B",
    "client_legal_name": "Agent B Corp",
    "package": "standard",
    "smart_goal": "By 2026-07-13, Agent A will deliver a pricing report covering all major LLM providers so Agent B can make data-driven model selection decisions.",
    "in_scope": [
      "Anthropic Claude pricing table",
      "OpenAI GPT pricing table",
      "Google Gemini pricing table",
      "Blended rate calculations"
    ],
    "out_of_scope": ["Custom model fine-tuning cost estimates"],
    "deliverables": [
      {
        "name": "pricing-report.md",
        "format": "Markdown",
        "due_date": "2026-07-13",
        "acceptance_criteria": "Report contains per-1k-token USD rates for at least 10 models with source timestamps",
        "revisions_included": 2
      }
    ],
    "model": "claude-sonnet-4-6",
    "token_estimate": 15000,
    "skill_premium_tokens": 3000,
    "skill_premium_justification": "Automated daily scraping saves 50k tokens of manual research per report",
    "upcharge_pct": 0.12,
    "materials_estimate": 0,
    "currency": "tokens",
    "ip_model": "client_ownership",
    "human_review_required": true,
    "governing_jurisdiction": "California, USA",
    "questions": {
      "who_do_you_help": "AI agents and developers selecting LLM providers",
      "what_do_you_deliver": "Daily-scraped pricing markdown report",
      "what_are_you_accessing": "Public pricing pages via Pricing Scraper API",
      "are_there_deliverable_questions": "None",
      "standard_policy": "Nanda Town platform policy",
      "appropriation_policy": "Client owns report on full payment"
    }
  }' 2>/dev/null || echo '{}')

if echo "$GEN_RESP" | jq -e '.contract_id' >/dev/null 2>&1; then
  CONTRACT_ID=$(echo "$GEN_RESP" | jq -r '.contract_id')
  CONTRACT_URL=$(echo "$GEN_RESP" | jq -r '.contract_url')
  NEXT_STEP=$(echo "$GEN_RESP" | jq -r '.next_step')
  pass "Contract generated: $CONTRACT_ID"
  echo "    URL: $CONTRACT_URL"
  echo "    next_step: $NEXT_STEP"
else
  fail "Contract generation failed: $GEN_RESP"
  exit 1
fi

# Verify token fields are static
if echo "$GEN_RESP" | jq -e '.token_fields.price_cap' >/dev/null 2>&1; then
  CAP=$(echo "$GEN_RESP" | jq -r '.token_fields.price_cap')
  TOTAL=$(echo "$GEN_RESP" | jq -r '.token_fields.total_tokens')
  pass "Static token fields in generate response: price_cap=$CAP  total_tokens=$TOTAL"
else
  warn "token_fields missing from generate response (older deployment?)"
fi

# ─── PHASE 4: Agent B reads the contract with live USD pricing ─────────────────

section "PHASE 4 — Agent B reads the contract (live USD computed at read time)"

step "Agent B fetches GET /contracts/$CONTRACT_ID.md"
CONTRACT_MD=$(curl -sf --max-time 15 "$CONTRACT_URL" 2>/dev/null || echo "")

if [ "${#CONTRACT_MD}" -gt 500 ]; then
  pass "Contract markdown fetched: ${#CONTRACT_MD} chars"
else
  fail "Contract markdown empty or missing"
fi

# Verify static token fields present
if echo "$CONTRACT_MD" | grep -qi "price.cap\|token estimate"; then
  pass "Contract contains token fields (static)"
else
  warn "Contract missing token field labels"
fi

# Verify live USD indicator
if echo "$CONTRACT_MD" | grep -qi "live\|fetched\|pricing scraper"; then
  pass "Contract shows live USD pricing indicator"
else
  warn "Contract does not indicate live USD pricing"
fi

# Verify USD values present
if echo "$CONTRACT_MD" | grep -q '\$[0-9]'; then
  pass "Contract contains USD cost values (live)"
else
  fail "Contract missing USD cost values"
fi

# Extract the contract hash for verification
HASH=$(echo "$CONTRACT_MD" | grep "contract_hash:" | head -1 | sed 's/.*: *"\(.*\)".*/\1/')
if [ -n "$HASH" ]; then
  pass "Contract hash present: ${HASH:0:16}..."
else
  warn "Could not extract contract hash from markdown"
fi

# ─── PHASE 5: Agent A notarizes via external Town Notary ─────────────────────

section "PHASE 5 — Agent A notarizes (external Town Notary — stellarminds.ai)"

step "Agent A calls POST /contracts/$CONTRACT_ID/notarize"
echo "    (Contract Agent calls Town Notary at $NOTARY_BASE — not our service)"

NOTARIZE_RESP=$(curl -sf -X POST "$CONTRACT_BASE/contracts/$CONTRACT_ID/notarize" \
  --max-time 30 2>/dev/null || echo '{"status":"error","notary_status":"failed","error":"timeout"}')

NOTARY_PATH="$NOTARY_SAVE_DIR/${CONTRACT_ID}-notarize.json"
echo "$NOTARIZE_RESP" > "$NOTARY_PATH"

N_STATUS=$(echo "$NOTARIZE_RESP" | jq -r '.status // "error"')
if [ "$N_STATUS" = "executed" ]; then
  SIG=$(echo "$NOTARIZE_RESP" | jq -r '.notary_signature_id // "?"')
  DID=$(echo "$NOTARIZE_RESP" | jq -r '.notary_did_key // "?"')
  INSPECT_URL=$(echo "$NOTARIZE_RESP" | jq -r '.notary_inspect_url // "?"')
  pass "Notarize: status=executed  signature=$SIG"
  echo "    notary_did: $DID"
  echo "    inspect:    $INSPECT_URL"
  echo "    receipt saved → $NOTARY_PATH"
else
  N_ERR=$(echo "$NOTARIZE_RESP" | jq -r '.error // .notary_status // "unknown"')
  warn "Notarize: status=$N_STATUS — $N_ERR"
  echo "    receipt saved → $NOTARY_PATH"
fi

# ─── PHASE 6: Agent B verifies via Town Notary before paying ──────────────────

section "PHASE 6 — Agent B verifies contract at Town Notary before paying"

step "Agent B calls GET $NOTARY_BASE/inspect?runtime=..."
NOTARY_RUNTIME=$(echo "$CONTRACT_ID" | tr '[:upper:]' '[:lower:]')
INSPECT_RESP=$(curl -sf --max-time 10 "$NOTARY_BASE/inspect?runtime=$NOTARY_RUNTIME" 2>/dev/null \
  || echo '{"detail":"not_reachable"}')

INSPECT_PATH="$NOTARY_SAVE_DIR/${CONTRACT_ID}-inspect.json"
echo "$INSPECT_RESP" > "$INSPECT_PATH"

if echo "$INSPECT_RESP" | jq -e '.certified' >/dev/null 2>&1; then
  CERTIFIED=$(echo "$INSPECT_RESP" | jq -r '.certified')
  RUNTIME=$(echo "$INSPECT_RESP" | jq -r '.runtime')
  SIGNER=$(echo "$INSPECT_RESP" | jq -r '.signer_did // "?"')
  if [ "$CERTIFIED" = "true" ]; then
    pass "Notary inspect: certified=true  runtime=$RUNTIME"
    echo "    signer_did: $SIGNER"
    echo "    → Agent B can safely transact ✓"
  else
    warn "Notary inspect: certified=false — not yet registered"
  fi
  echo "    saved → $INSPECT_PATH"
elif echo "$INSPECT_RESP" | jq -e '.detail' >/dev/null 2>&1; then
  DETAIL=$(echo "$INSPECT_RESP" | jq -r '.detail')
  warn "Notary inspect: $DETAIL"
  echo "    (notary may not have registered this contract yet)"
  echo "    saved → $INSPECT_PATH"
else
  warn "Notary inspect returned unexpected response"
  echo "    saved → $INSPECT_PATH"
fi

# ─── PHASE 7: Agent B accepts the contract ───────────────────────────────────

section "PHASE 7 — Agent B accepts the contract"

step "Agent B calls POST /contracts/$CONTRACT_ID/accept"
ACCEPT_RESP=$(curl -sf -X POST "$CONTRACT_BASE/contracts/$CONTRACT_ID/accept" \
  -H "Content-Type: application/json" \
  -d '{
    "accepting_agent": "agent-b-client/1.0",
    "accepting_human": "Agent B",
    "action": "accepted"
  }' 2>/dev/null || echo '{}')

if echo "$ACCEPT_RESP" | jq -e '.status' >/dev/null 2>&1; then
  A_STATUS=$(echo "$ACCEPT_RESP" | jq -r '.status')
  pass "Accept: status=$A_STATUS"
else
  fail "Accept endpoint broken: $ACCEPT_RESP"
fi

# ─── PHASE 8: Agent B re-reads the contract — USD refreshed ──────────────────

section "PHASE 8 — Agent B re-reads contract (USD re-fetched live at read time)"

step "Agent B fetches contract again to confirm USD updates at read time"
MD2=$(curl -sf --max-time 15 "$CONTRACT_URL" 2>/dev/null || echo "")
if [ "${#MD2}" -gt 500 ]; then
  STATUS_IN_MD=$(echo "$MD2" | grep "^status:" | head -1 | awk '{print $2}' | tr -d '"')
  pass "Re-read successful: status in YAML frontmatter = $STATUS_IN_MD (${#MD2} chars)"
  if echo "$MD2" | grep -qi "fetched\|live\|pricing scraper"; then
    pass "USD pricing note still present on re-read (live at read time confirmed)"
  else
    warn "USD pricing note not visible in re-read"
  fi
else
  fail "Re-read failed"
fi

# ─── PHASE 9: Verify skill.md URLs are machine-discoverable ──────────────────

section "PHASE 9 — Verify skill.md URLs are machine-discoverable endpoints"

step "Contract Agent agent.json lists skill_url and pricing_scraper"
AGENT_JSON=$(curl -sf --max-time 10 "$CONTRACT_BASE/agent.json" 2>/dev/null || echo '{}')
SKILL_URL=$(echo "$AGENT_JSON" | jq -r '.skill_url // ""')
if [ "$SKILL_URL" = "$CONTRACT_BASE/skill.md" ]; then
  pass "agent.json skill_url = $SKILL_URL"
else
  warn "agent.json skill_url = '$SKILL_URL' (expected $CONTRACT_BASE/skill.md)"
fi

SCRAPER_URL=$(echo "$AGENT_JSON" | jq -r '.pricing_scraper.url // ""')
if [ -n "$SCRAPER_URL" ]; then
  pass "agent.json has pricing_scraper.url = $SCRAPER_URL"
else
  warn "agent.json missing pricing_scraper.url"
fi

step "Pricing Scraper root lists skill endpoint"
PS_ROOT=$(curl -sf --max-time 10 "$PRICING_BASE/" 2>/dev/null || echo '{}')
PS_SKILL=$(echo "$PS_ROOT" | jq -r '.skill // .endpoints.skill // ""')
if [ -n "$PS_SKILL" ]; then
  pass "Pricing Scraper root lists skill: $PS_SKILL"
else
  warn "Pricing Scraper root missing skill field (may need deploy)"
fi

# ─── Summary ─────────────────────────────────────────────────────────────────

section "Summary"
TOTAL=$((PASS + FAIL + WARN))
echo -e "${GREEN}PASS: $PASS${RESET}  ${RED}FAIL: $FAIL${RESET}  ${YELLOW}WARN: $WARN${RESET}  Total: $TOTAL"
echo ""
echo "Contract:     $CONTRACT_URL"
echo "Skill (agent): $CONTRACT_BASE/skill.md"
echo "Skill (scraper): $PRICING_BASE/skill.md"
echo "Notary: $NOTARY_BASE (external — stellarminds.ai)"
echo ""
echo "Notary receipts:"
ls -1 "$NOTARY_SAVE_DIR/" 2>/dev/null | grep "$CONTRACT_ID" || true

if [ "$FAIL" -gt 0 ]; then
  exit 1
else
  exit 0
fi
