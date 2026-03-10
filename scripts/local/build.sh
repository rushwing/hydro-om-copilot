#!/usr/bin/env bash
# =============================================================================
# Hydro O&M Copilot — Local production build + lint
#
# Runs:
#   1. Backend:  ruff lint
#   2. Frontend: TypeScript type-check
#   3. Frontend: ESLint
#   4. Frontend: Vite production build  → frontend/dist/
#
# Usage: bash scripts/local/build.sh [--skip-lint] [--frontend-only]
# Exit code non-zero if any step fails.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
log_fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }
log_step()  { echo -e "\n${BOLD}▸ $*${NC}"; }

SKIP_LINT=false
FRONTEND_ONLY=false
ERRORS=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-lint)     SKIP_LINT=true ;;
        --frontend-only) FRONTEND_ONLY=true ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  Hydro O&M Copilot — Build${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# ── Backend lint ──────────────────────────────────────────────────────────────
if [[ "$FRONTEND_ONLY" != true && "$SKIP_LINT" != true ]]; then
    log_step "Backend lint (ruff)"
    if uv tool run ruff check "$PROJECT_ROOT/backend/"; then
        log_ok "ruff — no issues"
    else
        log_fail "ruff found issues"
        (( ERRORS++ )) || true
    fi
fi

# ── Frontend type-check ───────────────────────────────────────────────────────
if [[ "$SKIP_LINT" != true ]]; then
    log_step "Frontend type-check (tsc --noEmit)"
    cd "$PROJECT_ROOT/frontend"
    if npm run type-check 2>&1; then
        log_ok "TypeScript — no type errors"
    else
        log_fail "TypeScript type errors found"
        (( ERRORS++ )) || true
    fi

    # ── Frontend ESLint ───────────────────────────────────────────────────────
    log_step "Frontend lint (ESLint)"
    if npm run lint 2>&1; then
        log_ok "ESLint — no issues"
    else
        log_fail "ESLint found issues"
        (( ERRORS++ )) || true
    fi
fi

# ── Frontend production build ─────────────────────────────────────────────────
log_step "Frontend production build (vite build)"
cd "$PROJECT_ROOT/frontend"
if npm run build 2>&1; then
    log_ok "Build complete — artifacts in frontend/dist/"
    du -sh dist/ 2>/dev/null || true
else
    log_fail "Vite build failed"
    (( ERRORS++ )) || true
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [[ "$ERRORS" -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}  Build passed (0 errors)${NC}"
else
    echo -e "${RED}${BOLD}  Build failed ($ERRORS error(s))${NC}"
fi
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

exit "$ERRORS"
