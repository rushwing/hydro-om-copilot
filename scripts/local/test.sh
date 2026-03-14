#!/usr/bin/env bash
# =============================================================================
# Hydro O&M Copilot — Run all tests
#
# Runs:
#   1. Backend pytest  (backend/tests/)
#   2. Frontend tsc    (type-check, acts as a compile-time test)
#   3. Frontend ESLint (static analysis)
#
# Usage: bash scripts/local/test.sh [--backend-only | --frontend-only] [-v]
# Exit code non-zero if any suite fails.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

GREEN='\033[0;32m'; RED='\033[0;31m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

log_ok()   { echo -e "${GREEN}[ OK ]${NC}  $*"; }
log_fail() { echo -e "${RED}[FAIL]${NC}  $*"; }
log_step() { echo -e "\n${BOLD}▸ $*${NC}"; }

BACKEND_ONLY=false
FRONTEND_ONLY=false
VERBOSE=false
ERRORS=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --backend-only)  BACKEND_ONLY=true ;;
        --frontend-only) FRONTEND_ONLY=true ;;
        -v|--verbose)    VERBOSE=true ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

PYTEST_FLAGS=("--tb=short")
[[ "$VERBOSE" == true ]] && PYTEST_FLAGS+=("-v")

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  Hydro O&M Copilot — Test Suite${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# ── Backend tests ─────────────────────────────────────────────────────────────
if [[ "$FRONTEND_ONLY" != true ]]; then
    log_step "Backend tests (pytest)"
    cd "$PROJECT_ROOT/backend"
    if uv run pytest "${PYTEST_FLAGS[@]}"; then
        log_ok "pytest passed"
    else
        log_fail "pytest failed"
        (( ERRORS++ )) || true
    fi
fi

# ── Frontend type-check ───────────────────────────────────────────────────────
if [[ "$BACKEND_ONLY" != true ]]; then
    log_step "Frontend unit tests (Vitest)"
    cd "$PROJECT_ROOT/frontend"
    if npm run test; then
        log_ok "Vitest passed"
    else
        log_fail "Vitest failed"
        (( ERRORS++ )) || true
    fi

    log_step "Frontend type-check (tsc --noEmit)"
    if npm run type-check; then
        log_ok "TypeScript type-check passed"
    else
        log_fail "TypeScript type errors"
        (( ERRORS++ )) || true
    fi

    log_step "Frontend lint (ESLint)"
    if npm run lint; then
        log_ok "ESLint passed"
    else
        log_fail "ESLint failed"
        (( ERRORS++ )) || true
    fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [[ "$ERRORS" -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}  All tests passed${NC}"
else
    echo -e "${RED}${BOLD}  $ERRORS test suite(s) failed${NC}"
fi
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

exit "$ERRORS"
