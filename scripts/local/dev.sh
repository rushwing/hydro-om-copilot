#!/usr/bin/env bash
# =============================================================================
# Hydro O&M Copilot — Start local development servers
#
# Starts:
#   - Backend:  uvicorn on http://localhost:8000  (hot-reload enabled)
#   - Frontend: vite dev on   http://localhost:5173 (HMR enabled)
#
# Usage: bash scripts/local/dev.sh [--backend-only | --frontend-only]
# CTRL-C kills both processes cleanly.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()   { echo -e "${GREEN}[ OK ]${NC}  $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }

BACKEND_ONLY=false
FRONTEND_ONLY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --backend-only)  BACKEND_ONLY=true ;;
        --frontend-only) FRONTEND_ONLY=true ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

# ── Checks ────────────────────────────────────────────────────────────────────
if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
    log_warn ".env not found — run scripts/local/env-setup.sh first"
    exit 1
fi

if grep -q 'ANTHROPIC_API_KEY=sk-ant-\.\.\.' "$PROJECT_ROOT/.env" 2>/dev/null; then
    log_warn "ANTHROPIC_API_KEY still has placeholder value in .env"
    log_warn "Diagnosis calls will fail until you set a real key."
fi

if [[ ! -f "$PROJECT_ROOT/backend/.venv/bin/uvicorn" ]]; then
    log_warn "Backend venv not found — run scripts/local/env-setup.sh first"
    exit 1
fi

if [[ ! -d "$PROJECT_ROOT/frontend/node_modules" ]]; then
    log_warn "node_modules not found — run scripts/local/env-setup.sh first"
    exit 1
fi

PIDS=()

cleanup() {
    echo ""
    log_info "Shutting down dev servers…"
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
    echo -e "${GREEN}Done.${NC}"
}
trap cleanup EXIT INT TERM

# ── Backend ───────────────────────────────────────────────────────────────────
if [[ "$FRONTEND_ONLY" != true ]]; then
    echo ""
    log_ok "Starting backend  →  http://localhost:8000"
    log_info "  Docs: http://localhost:8000/docs"
    (
        cd "$PROJECT_ROOT/backend"
        # shellcheck disable=SC1091
        source .venv/bin/activate
        # Load .env into environment
        set -a; source "$PROJECT_ROOT/.env"; set +a
        uvicorn app.main:app \
            --host 0.0.0.0 \
            --port 8000 \
            --reload \
            --reload-dir app \
            2>&1 | sed 's/^/[backend] /'
    ) &
    PIDS+=($!)
fi

# ── Frontend ──────────────────────────────────────────────────────────────────
if [[ "$BACKEND_ONLY" != true ]]; then
    log_ok "Starting frontend →  http://localhost:5173"
    (
        cd "$PROJECT_ROOT/frontend"
        npm run dev 2>&1 | sed 's/^/[frontend] /'
    ) &
    PIDS+=($!)
fi

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}  Dev servers running. Press CTRL-C to stop.${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Wait for all background processes
wait "${PIDS[@]}"
