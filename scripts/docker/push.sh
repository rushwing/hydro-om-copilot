#!/usr/bin/env bash
# =============================================================================
# Hydro O&M Copilot — Push Docker images to registry
#
# Pushes all tags produced by build.sh to the configured registry.
# Run `docker login <registry>` before calling this script.
#
# Environment variables:
#   REGISTRY   Required. Registry prefix, e.g. registry.example.com/hydro
#   IMAGE_TAG  Tag to push (default: git short SHA)
#
# Usage:
#   REGISTRY=registry.example.com/hydro bash scripts/docker/push.sh
#   REGISTRY=registry.example.com/hydro IMAGE_TAG=v1.2.0 bash scripts/docker/push.sh
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

if [[ -z "${REGISTRY:-}" ]]; then
    log_fail "REGISTRY environment variable is required."
    echo ""
    echo "  Example:"
    echo "    REGISTRY=registry.example.com/hydro bash scripts/docker/push.sh"
    exit 1
fi

GIT_SHA="$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown")"
VERSION="$(grep '^version' "$PROJECT_ROOT/backend/pyproject.toml" \
           | head -1 | sed 's/.*= *"\(.*\)"/\1/')"
TAG_SHA="${IMAGE_TAG:-${GIT_SHA}}"
TAG_VER="${IMAGE_TAG:-${VERSION}}"
REG="${REGISTRY%/}"  # strip trailing slash

IMAGES=(
    "${REG}/hydro-om-backend:${TAG_SHA}"
    "${REG}/hydro-om-backend:${TAG_VER}"
    "${REG}/hydro-om-backend:latest"
    "${REG}/hydro-om-frontend:${TAG_SHA}"
    "${REG}/hydro-om-frontend:${TAG_VER}"
    "${REG}/hydro-om-frontend:latest"
)

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  Hydro O&M Copilot — Push Images${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log_info "Registry: $REG"
log_info "Tags    : $TAG_SHA  $TAG_VER  latest"
echo ""

# Verify local images exist before pushing
MISSING=0
for img in "${IMAGES[@]}"; do
    if ! docker image inspect "$img" &>/dev/null; then
        log_warn "Local image not found: $img"
        log_warn "  → Run scripts/docker/build.sh first"
        (( MISSING++ )) || true
    fi
done
if [[ "$MISSING" -gt 0 ]]; then
    log_fail "$MISSING image(s) not built locally. Aborting."
    exit 1
fi

# Push all tags
ERRORS=0
for img in "${IMAGES[@]}"; do
    log_info "Pushing $img …"
    if docker push "$img"; then
        log_ok "$img"
    else
        log_fail "Failed to push $img"
        (( ERRORS++ )) || true
    fi
done

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [[ "$ERRORS" -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}  All images pushed successfully.${NC}"
else
    echo -e "${RED}${BOLD}  $ERRORS push(es) failed.${NC}"
fi
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

exit "$ERRORS"
