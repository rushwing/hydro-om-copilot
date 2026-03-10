#!/usr/bin/env bash
# =============================================================================
# Hydro O&M Copilot — Local environment setup
# Checks prerequisites, creates .env, installs backend + frontend dependencies.
#
# Usage: bash scripts/local/env-setup.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()   { echo -e "${GREEN}[ OK ]${NC}  $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_fail() { echo -e "${RED}[FAIL]${NC}  $*"; }
log_step() { echo -e "\n${BOLD}▸ $*${NC}"; }

ERRORS=0

check_cmd() {
    local cmd="$1" label="${2:-$1}"
    if command -v "$cmd" &>/dev/null; then
        local ver; ver="$("$cmd" --version 2>&1 | head -1)"
        log_ok "$label — $ver"
    else
        log_fail "$label not found"
        (( ERRORS++ )) || true
    fi
}

check_python_version() {
    if command -v python3.11 &>/dev/null; then
        local ver; ver="$(python3.11 --version 2>&1)"
        log_ok "python3.11 — $ver"
    elif command -v python3 &>/dev/null; then
        local ver; ver="$(python3 --version 2>&1)"
        local minor; minor="$(python3 -c 'import sys; print(sys.version_info.minor)')"
        if [[ "$minor" -ge 11 ]]; then
            log_ok "python3 (≥3.11) — $ver"
        else
            log_fail "Python 3.11+ required, found $ver"
            log_fail "  Install: https://python.org/downloads  or  dnf install python3.11"
            (( ERRORS++ )) || true
        fi
    else
        log_fail "Python 3.11+ not found"
        (( ERRORS++ )) || true
    fi
}

check_node_version() {
    if command -v node &>/dev/null; then
        local ver; ver="$(node --version)"
        local major; major="${ver#v}"; major="${major%%.*}"
        if [[ "$major" -ge 18 ]]; then
            log_ok "node — $ver"
        else
            log_warn "Node.js $ver found; ≥18 recommended. Install Node.js 20: https://nodejs.org"
        fi
    else
        log_fail "node not found — Install Node.js 20: https://nodejs.org/en/download"
        (( ERRORS++ )) || true
    fi
}

# ── Header ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  Hydro O&M Copilot — Local Environment Setup${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# ── Prerequisites ─────────────────────────────────────────────────────────────
log_step "Checking prerequisites"
check_python_version
check_cmd uv         "uv (Python package manager)"
check_node_version
check_cmd npm        "npm"
check_cmd git        "git"

if command -v tesseract &>/dev/null; then
    log_ok "tesseract — $(tesseract --version 2>&1 | head -1)  (image OCR enabled)"
else
    log_warn "tesseract not found — image upload feature will be disabled at runtime"
    log_warn "  macOS:  brew install tesseract tesseract-lang"
    log_warn "  Ubuntu: apt install tesseract-ocr tesseract-ocr-chi-sim"
fi

if [[ "$ERRORS" -gt 0 ]]; then
    echo ""
    log_fail "$ERRORS required tool(s) missing. Please install them and re-run."
    echo ""
    echo "  uv:       curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  Node 20:  https://nodejs.org/en/download"
    exit 1
fi

# ── .env ──────────────────────────────────────────────────────────────────────
log_step "Configuring .env"
cd "$PROJECT_ROOT"

if [[ ! -f .env ]]; then
    cp .env.example .env
    log_ok ".env created from .env.example"
    log_warn "ACTION REQUIRED: edit .env and set ANTHROPIC_API_KEY before starting"
else
    log_ok ".env already exists"
    if grep -q 'ANTHROPIC_API_KEY=sk-ant-\.\.\.' .env 2>/dev/null; then
        log_warn "ANTHROPIC_API_KEY still has placeholder value — update it in .env"
    fi
fi

# ── Backend dependencies ───────────────────────────────────────────────────────
log_step "Installing backend dependencies"
cd "$PROJECT_ROOT/backend"
uv sync --extra dev
log_ok "Backend dependencies installed (see backend/.venv/)"

# ── Frontend dependencies ──────────────────────────────────────────────────────
log_step "Installing frontend dependencies"
cd "$PROJECT_ROOT/frontend"
npm install
log_ok "Frontend dependencies installed (see frontend/node_modules/)"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}  Setup complete!${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Next steps:"
echo "    1. Edit .env  →  set ANTHROPIC_API_KEY"
echo "    2. bash scripts/local/ingest.sh       # populate knowledge base"
echo "    3. bash scripts/local/dev.sh          # start backend + frontend dev servers"
echo ""
echo "  Other commands:"
echo "    bash scripts/local/build.sh           # lint + prod build"
echo "    bash scripts/local/test.sh            # run all tests"
echo ""
