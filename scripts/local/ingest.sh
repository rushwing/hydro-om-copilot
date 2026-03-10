#!/usr/bin/env bash
# =============================================================================
# Hydro O&M Copilot — Knowledge base ingestion (local)
#
# Wraps scripts/ingest_kb.py with sensible defaults.
#
# Usage:
#   bash scripts/local/ingest.sh                  # default KB dir from .env
#   bash scripts/local/ingest.sh --reset          # drop & rebuild all indexes
#   bash scripts/local/ingest.sh --kb-dir <path>  # custom KB directory
#
# All extra arguments are forwarded to ingest_kb.py.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()   { echo -e "${GREEN}[ OK ]${NC}  $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }

if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
    log_warn ".env not found — run scripts/local/env-setup.sh first"
    exit 1
fi

if [[ ! -f "$PROJECT_ROOT/backend/.venv/bin/python" ]]; then
    log_warn "Backend venv not found — run scripts/local/env-setup.sh first"
    exit 1
fi

# Load .env so KB_DOCS_DIR etc. are available
set -a; source "$PROJECT_ROOT/.env"; set +a

KB_DIR="${KB_DOCS_DIR:-$PROJECT_ROOT/knowledge_base/docs_internal}"
log_info "Knowledge base directory: $KB_DIR"

if [[ ! -d "$KB_DIR" ]]; then
    log_warn "KB directory not found: $KB_DIR"
    log_warn "Create it and add markdown documents, then re-run."
    exit 1
fi

DOC_COUNT="$(find "$KB_DIR" -name '*.md' | wc -l | tr -d ' ')"
log_info "Found $DOC_COUNT markdown document(s)"

echo ""
echo -e "${BOLD}▸ Running ingest_kb.py…${NC}"

cd "$PROJECT_ROOT/backend"
uv run "$PROJECT_ROOT/scripts/ingest_kb.py" \
    --kb-dir "$KB_DIR" \
    "$@"

echo ""
log_ok "Knowledge base ingestion complete."
log_info "Vector store: ${CHROMA_PERSIST_DIR:-./knowledge_base/vector_store}"
