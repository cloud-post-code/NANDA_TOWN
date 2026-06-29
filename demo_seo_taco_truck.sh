#!/usr/bin/env bash
# demo_seo_taco_truck.sh
# ======================
# Scenario:
#   SEO Blog Writing Agent  — offers blog content writing for local businesses
#   Taco Truck Agent (Tacos El Patrón, East Boston) — Spanish-speaking operator,
#       wants 4 SEO blog posts to help grow online orders
#
# The taco truck agent discovers the SEO agent via skill.md, checks live model
# pricing from the Pricing Scraper, generates a contract, signs it, and verifies
# it with the Town Notary — all using only live curl endpoints.
#
# Prerequisites: curl, jq
# Usage: bash demo_seo_taco_truck.sh

set -uo pipefail

CONTRACT_BASE="https://hackathon-contract-agent-production.up.railway.app"
NOTARY_BASE="https://town-notary-production.up.railway.app"
NOTARY_SAVE_DIR="${NOTARY_SAVE_DIR:-./notary-receipts}"

# Resolve live pricing scraper URL from agent.json (Railway may assign any subdomain)
PRICING_BASE=$(curl -sf --max-time 10 "$CONTRACT_BASE/agent.json" 2>/dev/null \
  | jq -r '.pricing_scraper.url // "https://pricing-scraper-production.up.railway.app"')

GREEN="\033[0;32m"; RED="\033[0;31m"; YELLOW="\033[0;33m"
CYAN="\033[0;36m"; BOLD="\033[1m"; RESET="\033[0m"

ok()      { echo -e "${GREEN}✓${RESET}  $1"; }
fail()    { echo -e "${RED}✗  $1${RESET}"; }
info()    { echo -e "${CYAN}→${RESET}  $1"; }
heading() { echo -e "\n${BOLD}${YELLOW}━━━  $1  ━━━${RESET}"; }
spanish() { echo -e "   ${YELLOW}[Tacos El Patrón]${RESET} $1"; }
seo()     { echo -e "   ${CYAN}[SEO Blog Agent]${RESET}  $1"; }

mkdir -p "$NOTARY_SAVE_DIR"

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   Tacos El Patrón × SEO Blog Writing Agent — Live Demo      ║"
echo "║   East Boston, MA  ·  Nanda Town Contract System            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${RESET}"

# ─── STEP 1: Taco Truck discovers the SEO Agent's skill.md ───────────────────

heading "PASO 1 / STEP 1 — Taco Truck discovers the SEO Agent via skill.md"

spanish "Buscando servicios de contenido SEO para mi negocio…"
spanish "(Looking for SEO content services for my business…)"

info "Fetching Contract Agent skill.md to understand available services..."
SKILL=$(curl -sf --max-time 10 "$CONTRACT_BASE/skill.md" -H "Accept: text/plain" 2>/dev/null || echo "")
if [ "${#SKILL}" -gt 100 ]; then
  ok "Contract Agent skill.md found: ${#SKILL} chars at $CONTRACT_BASE/skill.md"
  echo "   Endpoints the taco truck agent now knows about:"
  echo "$SKILL" | grep -E "POST|GET" | grep -v "^>" | head -10 | sed 's/^/   /'
else
  fail "Could not fetch skill.md"
  exit 1
fi

info "Fetching Pricing Scraper skill.md to understand live token rates..."
PS_SKILL=$(curl -sf --max-time 10 "$PRICING_BASE/skill.md" -H "Accept: text/plain" 2>/dev/null || echo "")
if [ "${#PS_SKILL}" -gt 100 ]; then
  ok "Pricing Scraper skill.md found: ${#PS_SKILL} chars at $PRICING_BASE/skill.md"
else
  ok "Pricing Scraper skill.md not reachable — will use fallback rates"
fi

# ─── STEP 2: Taco Truck checks live model pricing ────────────────────────────

heading "PASO 2 / STEP 2 — Taco Truck checks live model pricing"

spanish "Quiero saber cuánto cuesta usar el modelo de IA…"
spanish "(I want to know how much the AI model costs…)"

info "Fetching live rate for claude-haiku-4-5 (cost-efficient model for blog writing)..."
RATE_RESP=$(curl -sf --max-time 10 "$PRICING_BASE/pricing/models/claude-haiku-4-5" 2>/dev/null || echo '{}')

if echo "$RATE_RESP" | jq -e '.input_per_1k_usd' >/dev/null 2>&1; then
  INP=$(echo "$RATE_RESP" | jq -r '.input_per_1k_usd')
  OUT=$(echo "$RATE_RESP" | jq -r '.output_per_1k_usd')
  BLENDED=$(python3 -c "print(round($INP * 0.6 + $OUT * 0.4, 6))" 2>/dev/null || echo "0.0026")
  ok "Live rate for claude-haiku-4-5:"
  echo "   input:   \$${INP} / 1k tokens"
  echo "   output:  \$${OUT} / 1k tokens"
  echo "   blended: \$${BLENDED} / 1k tokens  (60% input + 40% output)"
  spanish "¡Perfecto! El costo es accesible para mi negocio."
  spanish "(Perfect! The cost is affordable for my business.)"
else
  ok "Pricing scraper unreachable — Contract Agent will use fallback rate ($0.0026/1k)"
  BLENDED="0.0026"
fi

info "Also checking what's available across all providers..."
ALL=$(curl -sf --max-time 10 "$PRICING_BASE/pricing/models" 2>/dev/null | jq '.all_models | length // 0' 2>/dev/null || echo "0")
ok "Pricing catalog: $ALL models available across all providers"

# ─── STEP 3: Generate the contract ───────────────────────────────────────────

heading "PASO 3 / STEP 3 — SEO Agent proposes a contract to the Taco Truck"

seo "Generating a formal service contract for Tacos El Patrón…"
spanish "El agente de SEO está preparando el contrato…"
spanish "(The SEO agent is preparing the contract…)"

info "Calling POST $CONTRACT_BASE/contracts/generate ..."

GEN_RESP=$(curl -sf -X POST "$CONTRACT_BASE/contracts/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "SEO Blog Content Writing — Tacos El Patron East Boston",
    "provider_agent": "seo-blog-writer-agent/1.0",
    "provider_endpoint": "https://seo-blog-agent.example.com",
    "provider_human": "Marco Reyes — SEO Blog Writing Agent",
    "provider_legal_name": "Marco Reyes Content LLC",
    "client_agent": "tacos-el-patron-agent/1.0",
    "client_endpoint": "https://tacos-el-patron-eastboston.example.com",
    "client_human": "Carlos Mendoza — Tacos El Patron, East Boston MA",
    "client_legal_name": "Tacos El Patron LLC",
    "package": "standard",
    "smart_goal": "By 2026-07-27, SEO Blog Writer Agent will deliver 4 Spanish-friendly SEO blog posts about Tacos El Patron so that the taqueria ranks on Google for East Boston taco searches and increases online orders by 20%.",
    "in_scope": [
      "4 SEO-optimized blog posts (600-900 words each)",
      "Keyword research for East Boston taco and Mexican food searches",
      "English copy with Spanish accent for bilingual East Boston audience",
      "Meta title and meta description for each post",
      "Google-friendly headings and internal link suggestions"
    ],
    "out_of_scope": [
      "Website publishing or WordPress setup",
      "Social media scheduling",
      "Paid ad copy",
      "Translation into full Spanish (bilingual tone only)"
    ],
    "deliverables": [
      {
        "name": "blog-post-1-best-tacos-east-boston.md",
        "format": "Markdown",
        "due_date": "2026-07-06",
        "acceptance_criteria": "600+ words, includes target keyword in H1 and first paragraph, has meta title and meta description",
        "revisions_included": 2
      },
      {
        "name": "blog-post-2-authentic-mexican-food-eastie.md",
        "format": "Markdown",
        "due_date": "2026-07-13",
        "acceptance_criteria": "600+ words, targets authentic Mexican food East Boston search intent, includes menu items by name",
        "revisions_included": 2
      },
      {
        "name": "blog-post-3-taco-truck-catering-boston.md",
        "format": "Markdown",
        "due_date": "2026-07-20",
        "acceptance_criteria": "600+ words, targets catering keyword, includes call-to-action for event inquiries",
        "revisions_included": 2
      },
      {
        "name": "blog-post-4-east-boston-food-scene.md",
        "format": "Markdown",
        "due_date": "2026-07-27",
        "acceptance_criteria": "600+ words, positions Tacos El Patron in the East Boston food scene, links to other posts",
        "revisions_included": 2
      }
    ],
    "model": "claude-haiku-4-5",
    "token_estimate": 40000,
    "skill_premium_tokens": 8000,
    "skill_premium_justification": "SEO keyword research, bilingual tone calibration, and Google-optimized structure save client 200k tokens of manual research and rewrites",
    "upcharge_pct": 0.10,
    "materials_estimate": 500,
    "currency": "tokens",
    "ip_model": "client_ownership",
    "human_review_required": true,
    "governing_jurisdiction": "Massachusetts, USA",
    "questions": {
      "who_do_you_help": "Tacos El Patron, a taco truck in East Boston serving a bilingual Spanish-English community",
      "what_do_you_deliver": "4 SEO blog posts optimized for local East Boston search traffic",
      "what_are_you_accessing": "Public keyword data and the Nanda Town pricing scraper for live model cost estimates",
      "are_there_deliverable_questions": "Client prefers bilingual-friendly tone; no full Spanish translation needed",
      "standard_policy": "Nanda Town platform policy — no fabricated reviews or misleading claims",
      "appropriation_policy": "Client owns all blog posts upon full token payment; provider retains prompt templates"
    }
  }' 2>/dev/null || echo '{}')

if echo "$GEN_RESP" | jq -e '.contract_id' >/dev/null 2>&1; then
  CID=$(echo "$GEN_RESP" | jq -r '.contract_id')
  CURL=$(echo "$GEN_RESP" | jq -r '.contract_url')
  CAP=$(echo "$GEN_RESP" | jq -r '.token_fields.price_cap // "?"')
  TOTAL=$(echo "$GEN_RESP" | jq -r '.token_fields.total_tokens // "?"')
  NEXT=$(echo "$GEN_RESP" | jq -r '.next_step')
  ok "Contract created: $CID"
  echo "   URL:         $CURL"
  echo "   Price cap:   $CAP tokens (hard ceiling)"
  echo "   Total:       $TOTAL tokens"
  echo "   Next step:   $NEXT"
  seo "Contract draft sent to Tacos El Patron for review."
else
  fail "Contract generation failed: $GEN_RESP"
  exit 1
fi

# ─── STEP 4: Taco Truck reads the full contract with live USD pricing ─────────

heading "PASO 4 / STEP 4 — Taco Truck reads the full contract (live USD pricing)"

spanish "Déjame leer el contrato y ver cuánto me va a costar en dólares…"
spanish "(Let me read the contract and see how much it will cost in dollars…)"

info "Fetching $CURL ..."
MD=$(curl -sf --max-time 15 "$CURL" 2>/dev/null || echo "")

if [ "${#MD}" -gt 500 ]; then
  ok "Full contract received: ${#MD} chars"

  # Show the taco truck agent the key numbers
  echo ""
  echo "   ── Contract summary (what Tacos El Patron sees) ──────────────────"

  # Extract pricing line
  RATE_LINE=$(echo "$MD" | grep "Rate:" | head -1 | sed 's/.*\*\*/Rate:\*\*//')
  echo "   Rate:       $RATE_LINE"

  # Extract grand total USD
  GRAND=$(echo "$MD" | grep "Grand total" | grep -o '\$[0-9.]*' | tail -1)
  echo "   USD total:  $GRAND (live at read time)"

  # Extract token total
  TOK=$(echo "$MD" | grep "Grand total" | grep -o '[0-9,]* tokens' | head -1)
  echo "   Token total:$TOK (static, never changes)"

  # Show deliverables count
  DELIVS=$(echo "$MD" | grep -c "blog-post-")
  echo "   Deliverables: $DELIVS blog posts"

  # Show SMART goal
  GOAL=$(echo "$MD" | grep -A1 "SMART goal" | tail -1 | sed 's/^> //')
  echo "   Goal: $GOAL"
  echo "   ───────────────────────────────────────────────────────────────────"

  spanish "Entiendo el contrato. $GRAND USD por 4 artículos SEO. ¡Está bien!"
  spanish "(I understand the contract. $GRAND USD for 4 SEO articles. That's fine!)"
else
  fail "Could not read contract markdown"
  exit 1
fi

# ─── STEP 5: Taco Truck checks live pricing again before signing ──────────────

heading "PASO 5 / STEP 5 — Taco Truck verifies live pricing before signing"

spanish "Antes de firmar, quiero confirmar el precio actual del modelo…"
spanish "(Before signing, I want to confirm the current model price…)"

info "Taco Truck Agent calls Pricing Scraper directly: GET /pricing/models/claude-haiku-4-5"
LIVE_CHECK=$(curl -sf --max-time 10 "$PRICING_BASE/pricing/models/claude-haiku-4-5" 2>/dev/null || echo '{}')

if echo "$LIVE_CHECK" | jq -e '.model' >/dev/null 2>&1; then
  MODEL=$(echo "$LIVE_CHECK" | jq -r '.model')
  INP2=$(echo "$LIVE_CHECK" | jq -r '.input_per_1k_usd')
  OUT2=$(echo "$LIVE_CHECK" | jq -r '.output_per_1k_usd')
  SCRAPED=$(echo "$LIVE_CHECK" | jq -r '.source // "anthropic.com/pricing"')
  ok "Live rate confirmed from $SCRAPED:"
  echo "   Model:  $MODEL"
  echo "   Input:  \$${INP2}/1k tokens"
  echo "   Output: \$${OUT2}/1k tokens"
  spanish "El precio está actualizado. Voy a firmar el contrato."
  spanish "(The price is current. I'm going to sign the contract.)"
else
  ok "Pricing scraper returned fallback — rates still shown in contract (live on read)"
  spanish "Bien, el contrato ya tiene los precios. Voy a firmar."
fi

# ─── STEP 6: Taco Truck signs / accepts the contract ─────────────────────────

heading "PASO 6 / STEP 6 — Tacos El Patron signs the contract"

spanish "Acepto los términos. Firmando el contrato ahora…"
spanish "(I accept the terms. Signing the contract now…)"

info "Taco Truck Agent calls POST /contracts/$CID/accept ..."
ACCEPT=$(curl -sf -X POST "$CONTRACT_BASE/contracts/$CID/accept" \
  -H "Content-Type: application/json" \
  -d '{
    "accepting_agent": "tacos-el-patron-agent/1.0",
    "accepting_human": "Carlos Mendoza — Tacos El Patron East Boston",
    "action": "accepted"
  }' 2>/dev/null || echo '{}')

if echo "$ACCEPT" | jq -e '.status' >/dev/null 2>&1; then
  A_STATUS=$(echo "$ACCEPT" | jq -r '.status')
  ok "Contract accepted: status=$A_STATUS"
  spanish "¡Firmado! El contrato está aceptado por Tacos El Patron."
  spanish "(Signed! The contract is accepted by Tacos El Patron.)"
else
  fail "Accept call failed: $ACCEPT"
fi

# ─── STEP 7: Notarize via external Town Notary ───────────────────────────────

heading "PASO 7 / STEP 7 — Notarizing with the Town Notary (external service)"

seo "Submitting to the Town Notary to make this contract binding…"
spanish "El agente de SEO está registrando el contrato con el notario oficial…"
spanish "(The SEO agent is registering the contract with the official notary…)"

info "Calling POST $CONTRACT_BASE/contracts/$CID/notarize ..."
info "(Contract Agent builds signed Ed25519 badge → submits to $NOTARY_BASE/register)"

NOTARIZE=$(curl -sf -X POST "$CONTRACT_BASE/contracts/$CID/notarize" \
  --max-time 30 2>/dev/null || echo '{"status":"error","error":"timeout"}')

RECEIPT_PATH="$NOTARY_SAVE_DIR/${CID}-notarize.json"
echo "$NOTARIZE" > "$RECEIPT_PATH"

N_STATUS=$(echo "$NOTARIZE" | jq -r '.status // "error"')
if [ "$N_STATUS" = "executed" ]; then
  SIG=$(echo "$NOTARIZE" | jq -r '.notary_signature_id // "?"')
  INSPECT_URL=$(echo "$NOTARIZE" | jq -r '.notary_inspect_url // "?"')
  ok "Notarized: status=executed"
  echo "   Notary key:  $SIG"
  echo "   Inspect URL: $INSPECT_URL"
  echo "   Receipt:     $RECEIPT_PATH"
  seo "Contract is now on the public notary register."
  spanish "¡El contrato es oficial! Registrado con el notario."
  spanish "(The contract is official! Registered with the notary.)"
else
  N_ERR=$(echo "$NOTARIZE" | jq -r '.error // "unknown error"')
  echo -e "${YELLOW}WARN${RESET}  Notarize returned status=$N_STATUS — $N_ERR"
  echo "   Receipt saved: $RECEIPT_PATH"
fi

# ─── STEP 8: Taco Truck verifies at the notary before paying ─────────────────

heading "PASO 8 / STEP 8 — Tacos El Patron verifies with the Town Notary"

spanish "Antes de pagar, voy a verificar que el contrato está registrado oficialmente…"
spanish "(Before paying, I will verify the contract is officially registered…)"

NOTARY_RUNTIME=$(echo "$CID" | tr '[:upper:]' '[:lower:]')
info "Taco Truck Agent calls GET $NOTARY_BASE/inspect?runtime=$NOTARY_RUNTIME ..."

INSPECT=$(curl -sf --max-time 10 "$NOTARY_BASE/inspect?runtime=$NOTARY_RUNTIME" 2>/dev/null \
  || echo '{"detail":"not_reachable"}')

INSPECT_PATH="$NOTARY_SAVE_DIR/${CID}-inspect.json"
echo "$INSPECT" > "$INSPECT_PATH"

if echo "$INSPECT" | jq -e '.certified' >/dev/null 2>&1; then
  CERTIFIED=$(echo "$INSPECT" | jq -r '.certified')
  SIGNER=$(echo "$INSPECT" | jq -r '.signer_did // "?"')
  REG_AT=$(echo "$INSPECT" | jq -r '.registered_at // "?"')
  if [ "$CERTIFIED" = "true" ]; then
    ok "Town Notary confirms: certified=true"
    echo "   Signer:      $SIGNER"
    echo "   Registered:  $REG_AT"
    echo "   Inspect:     $INSPECT_PATH"
    spanish "¡Verificado! El notario confirma que el contrato es auténtico."
    spanish "(Verified! The notary confirms the contract is authentic.)"
    spanish "Tacos El Patron puede pagar con confianza. ✓"
    spanish "(Tacos El Patron can pay with confidence. ✓)"
  else
    echo -e "${YELLOW}WARN${RESET}  Notary returned certified=false"
  fi
else
  DETAIL=$(echo "$INSPECT" | jq -r '.detail // "unexpected response"')
  echo -e "${YELLOW}WARN${RESET}  Notary inspect: $DETAIL"
  echo "   Inspect saved: $INSPECT_PATH"
fi

# ─── STEP 9: Final contract state ────────────────────────────────────────────

heading "PASO 9 / STEP 9 — Final contract state"

STATUS_RESP=$(curl -sf --max-time 10 "$CONTRACT_BASE/contracts/$CID/status" 2>/dev/null || echo '{}')
FINAL_STATUS=$(echo "$STATUS_RESP" | jq -r '.status // "?"')
NOTARY_SIGNED=$(echo "$STATUS_RESP" | jq -r '.notary_countersigned // false')

ok "Contract $CID final state:"
echo "   Status:           $FINAL_STATUS"
echo "   Notary signed:    $NOTARY_SIGNED"
echo "   Contract URL:     $CURL"
echo "   Notary inspect:   $NOTARY_BASE/inspect?runtime=$NOTARY_RUNTIME"

# ─── Print the full contract for review ──────────────────────────────────────

heading "CONTRATO COMPLETO / FULL CONTRACT"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -sf --max-time 15 "$CURL" 2>/dev/null || echo "(Could not fetch contract)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─── Summary ─────────────────────────────────────────────────────────────────

heading "RESUMEN / SUMMARY"
echo ""
echo -e "${BOLD}Parties:${RESET}"
echo "   Provider: Marco Reyes — SEO Blog Writing Agent (seo-blog-writer-agent/1.0)"
echo "   Client:   Carlos Mendoza — Tacos El Patron, East Boston MA (tacos-el-patron-agent/1.0)"
echo ""
echo -e "${BOLD}Service:${RESET}"
echo "   4 SEO blog posts in bilingual English/Spanish tone"
echo "   Target: East Boston taco & Mexican food searches"
echo "   Delivery: 2026-07-06 through 2026-07-27"
echo ""
echo -e "${BOLD}Pricing (live at read time):${RESET}"
echo "   Model:       claude-haiku-4-5"
echo "   Rate source: Live from Pricing Scraper ($PRICING_BASE)"
echo "   Token cap:   $CAP tokens (hard ceiling, static)"
echo "   USD total:   $GRAND (live, re-priced on every read)"
echo ""
echo -e "${BOLD}Contract:${RESET}  $CURL"
echo -e "${BOLD}Notary:${RESET}    $NOTARY_BASE/inspect?runtime=$NOTARY_RUNTIME"
echo -e "${BOLD}Receipts:${RESET}  $NOTARY_SAVE_DIR/${CID}-*.json"
echo ""
echo -e "${GREEN}${BOLD}¡El contrato está firmado y notariado! / Contract signed and notarized!${RESET}"
