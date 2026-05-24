#!/usr/bin/env bash
# Pilot smoke — проверка живого API (local / staging / prod).
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CSV="${REPO_ROOT}/tests/fixtures/banks/sber_sample.csv"
TMP_PDF="${TMPDIR:-/tmp}/pilot-smoke-report.pdf"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

step() {
  echo ""
  echo -e "${GREEN}==>${NC} $1"
}

fail() {
  echo -e "${RED}FAIL:${NC} $1" >&2
  exit 1
}

if [[ ! -f "$CSV" ]]; then
  fail "CSV fixture not found: $CSV"
fi

step "Health check"
curl -sf "$BASE_URL/health" | grep -q '"status"' || fail "Health check failed"

step "1/8 Register"
REGISTER_JSON=$(curl -sf -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"pilot-$(date +%s)@example.com\",\"company_name\":\"Pilot Smoke Co\"}")
TOKEN=$(echo "$REGISTER_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
[[ -n "$TOKEN" ]] || fail "No access_token in register response"
AUTH="Authorization: Bearer $TOKEN"

step "2/8 Import bank CSV"
IMPORT_JSON=$(curl -sf -X POST "$BASE_URL/imports/bank" \
  -H "$AUTH" \
  -F "file=@${CSV}" \
  -F "bank_key=sber")
echo "$IMPORT_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status') in ('done','partial'), d"

step "3/8 Dashboard"
DASH=$(curl -sf "$BASE_URL/dashboard/today" -H "$AUTH")
echo "$DASH" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d.get('has_data') is True, d
assert d.get('balance') is not None, d
assert len(d['forecast']['days_preview']) >= 90, len(d['forecast']['days_preview'])
print(f\"  balance={d['balance']}\")
"

step "4/8 Create obligation"
curl -sf -X POST "$BASE_URL/obligations" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"due_date":"2026-12-01","amount":150000,"description":"Pilot smoke — аренда"}' \
  | python3 -c "import sys,json; json.load(sys.stdin)"

step "5/8 List obligations"
OBS=$(curl -sf "$BASE_URL/obligations" -H "$AUTH")
echo "$OBS" | python3 -c "
import sys, json
items = json.load(sys.stdin).get('obligations', [])
assert any('Pilot smoke' in (o.get('description') or '') for o in items), items
print(f\"  obligations={len(items)}\")
"

step "6/8 Invite viewer"
INVITE_EMAIL="viewer-$(date +%s)@example.com"
curl -sf -X POST "$BASE_URL/users" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${INVITE_EMAIL}\",\"role\":\"viewer\"}" \
  | python3 -c "import sys,json; json.load(sys.stdin)"

step "7/8 Audit log"
AUDIT=$(curl -sf "$BASE_URL/audit?limit=20" -H "$AUTH")
echo "$AUDIT" | python3 -c "
import sys, json
actions = [e['action'] for e in json.load(sys.stdin).get('entries', [])]
assert 'invite_user' in actions, actions
print(f\"  actions={actions[:5]}\")
"

step "8/8 Download PDF"
curl -sf "$BASE_URL/reports/weekly" -H "$AUTH" -o "$TMP_PDF"
file "$TMP_PDF" | grep -q PDF || fail "Downloaded file is not PDF"
echo "  saved: $TMP_PDF"

if [[ -n "${OPENROUTER_API_KEY:-}" ]]; then
  step "Optional: AI chat"
  CHAT=$(curl -sf -X POST "$BASE_URL/ai/chat" \
    -H "$AUTH" \
    -H "Content-Type: application/json" \
    -d '{"question":"Какой прогноз остатка на неделю?"}')
  echo "$CHAT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('answer'); print(f\"  provider={d.get('provider')}\")"
else
  echo ""
  echo "  (AI chat skipped — OPENROUTER_API_KEY not set)"
fi

echo ""
echo -e "${GREEN}Pilot smoke passed${NC} — $BASE_URL"
