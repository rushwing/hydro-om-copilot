#!/usr/bin/env bash
# =============================================================================
# Hydro O&M Copilot — Deploy via Docker Compose (production)
#
# Manages the production docker-compose.prod.yml stack.
#
# Usage:
#   bash scripts/docker/deploy-compose.sh up       # start (default)
#   bash scripts/docker/deploy-compose.sh down     # stop and remove containers
#   bash scripts/docker/deploy-compose.sh restart  # rolling restart
#   bash scripts/docker/deploy-compose.sh logs     # follow logs
#   bash scripts/docker/deploy-compose.sh status   # show container status
#   bash scripts/docker/deploy-compose.sh ingest   # run KB ingest inside backend
#
# Environment variables:
#   REGISTRY    Image registry prefix (must match what was used in build.sh)
#   IMAGE_TAG   Image tag to deploy (default: latest)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()   { echo -e "${GREEN}[ OK ]${NC}  $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_fail() { echo -e "${RED}[FAIL]${NC}  $*"; }

COMPOSE_FILE="$PROJECT_ROOT/docker-compose.prod.yml"
COMMAND="${1:-up}"

if [[ ! -f "$COMPOSE_FILE" ]]; then
    log_fail "docker-compose.prod.yml not found at $COMPOSE_FILE"
    exit 1
fi

if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
    log_warn ".env not found — copy .env.example → .env and set ANTHROPIC_API_KEY"
    exit 1
fi

export REGISTRY="${REGISTRY:-}"
export IMAGE_TAG="${IMAGE_TAG:-latest}"

cd "$PROJECT_ROOT"

case "$COMMAND" in

    up)
        echo ""
        echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${BOLD}  Hydro O&M Copilot — Deploy (docker-compose)${NC}"
        echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        log_info "Image tag : $IMAGE_TAG"
        log_info "Registry  : ${REGISTRY:-<local>}"
        echo ""

        docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

        echo ""
        log_ok "Stack started. Services:"
        docker compose -f "$COMPOSE_FILE" ps
        echo ""
        log_info "Frontend : http://localhost:80"
        log_info "Backend  : http://localhost:8000  (loopback only)"
        log_info "Qdrant   : http://localhost:6333   (loopback only)"
        echo ""
        log_info "Tail logs: bash scripts/docker/deploy-compose.sh logs"
        ;;

    down)
        log_info "Stopping stack…"
        docker compose -f "$COMPOSE_FILE" down
        log_ok "Stack stopped."
        ;;

    restart)
        log_info "Restarting stack…"
        docker compose -f "$COMPOSE_FILE" restart
        log_ok "Stack restarted."
        docker compose -f "$COMPOSE_FILE" ps
        ;;

    logs)
        exec docker compose -f "$COMPOSE_FILE" logs -f --tail=100
        ;;

    status)
        docker compose -f "$COMPOSE_FILE" ps
        ;;

    ingest)
        log_info "Running knowledge base ingestion inside backend container…"
        docker compose -f "$COMPOSE_FILE" exec backend \
            python3.11 -m scripts.ingest_kb \
            --kb-dir /app/knowledge_base/docs_internal \
            "${@:2}"
        log_ok "Ingestion complete."
        ;;

    *)
        echo "Usage: $0 {up|down|restart|logs|status|ingest}"
        exit 1
        ;;
esac
