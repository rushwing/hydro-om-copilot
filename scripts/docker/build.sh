#!/usr/bin/env bash
# =============================================================================
# Hydro O&M Copilot — Docker image build (CentOS Stream 9)
#
# Builds backend and frontend images using Dockerfile.centos variants.
# Images are tagged with:
#   - <name>:<git-sha>     (immutable, for K8s GitOps)
#   - <name>:<version>     (from pyproject.toml)
#   - <name>:latest        (mutable, for docker-compose convenience)
#
# Environment variables:
#   REGISTRY    Image registry prefix, e.g. registry.example.com/hydro
#               Leave empty for local-only images.
#   IMAGE_TAG   Override all tags with a single value (optional)
#   BUILD_ARGS  Additional docker build args (optional)
#
# Usage:
#   bash scripts/docker/build.sh                         # build both
#   bash scripts/docker/build.sh --backend               # backend only
#   bash scripts/docker/build.sh --frontend              # frontend only
#   REGISTRY=registry.example.com bash scripts/docker/build.sh
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
log_step() { echo -e "\n${BOLD}▸ $*${NC}"; }

BUILD_BACKEND=true
BUILD_FRONTEND=true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --backend)  BUILD_BACKEND=true;  BUILD_FRONTEND=false ;;
        --frontend) BUILD_FRONTEND=true; BUILD_BACKEND=false ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

# ── Compute tags ──────────────────────────────────────────────────────────────
GIT_SHA="$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown")"
VERSION="$(grep '^version' "$PROJECT_ROOT/backend/pyproject.toml" \
           | head -1 | sed 's/.*= *"\(.*\)"/\1/')"
REGISTRY="${REGISTRY:-}"
REG_PREFIX="${REGISTRY:+${REGISTRY}/}"

# Allow full override via IMAGE_TAG env
TAG_SHA="${IMAGE_TAG:-${GIT_SHA}}"
TAG_VER="${IMAGE_TAG:-${VERSION}}"
TAG_LATEST="latest"

make_tags() {
    local name="$1"
    local base="${REG_PREFIX}${name}"
    echo "${base}:${TAG_SHA}" "${base}:${TAG_VER}" "${base}:${TAG_LATEST}"
}

# ── Build args ────────────────────────────────────────────────────────────────
BUILD_DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  Hydro O&M Copilot — Docker Build (CentOS Stream 9)${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log_info "Git SHA  : $GIT_SHA"
log_info "Version  : $VERSION"
log_info "Registry : ${REGISTRY:-<local>}"
log_info "Tags     : $TAG_SHA  $TAG_VER  $TAG_LATEST"

# ── Backend image ─────────────────────────────────────────────────────────────
if [[ "$BUILD_BACKEND" == true ]]; then
    log_step "Building backend image"
    read -ra BACKEND_TAGS <<< "$(make_tags hydro-om-backend)"
    TAG_ARGS=()
    for t in "${BACKEND_TAGS[@]}"; do TAG_ARGS+=(-t "$t"); done

    docker build \
        "${TAG_ARGS[@]}" \
        --file "$PROJECT_ROOT/backend/Dockerfile.centos" \
        --label "org.opencontainers.image.created=${BUILD_DATE}" \
        --label "org.opencontainers.image.revision=${GIT_SHA}" \
        --label "org.opencontainers.image.version=${VERSION}" \
        --cache-from "${REG_PREFIX}hydro-om-backend:latest" \
        ${BUILD_ARGS:-} \
        "$PROJECT_ROOT/backend"

    log_ok "Backend image built:"
    for t in "${BACKEND_TAGS[@]}"; do echo "         $t"; done
fi

# ── Frontend image ────────────────────────────────────────────────────────────
if [[ "$BUILD_FRONTEND" == true ]]; then
    log_step "Building frontend image"
    read -ra FRONTEND_TAGS <<< "$(make_tags hydro-om-frontend)"
    TAG_ARGS=()
    for t in "${FRONTEND_TAGS[@]}"; do TAG_ARGS+=(-t "$t"); done

    docker build \
        "${TAG_ARGS[@]}" \
        --file "$PROJECT_ROOT/frontend/Dockerfile.centos" \
        --label "org.opencontainers.image.created=${BUILD_DATE}" \
        --label "org.opencontainers.image.revision=${GIT_SHA}" \
        --label "org.opencontainers.image.version=${VERSION}" \
        --cache-from "${REG_PREFIX}hydro-om-frontend:latest" \
        ${BUILD_ARGS:-} \
        "$PROJECT_ROOT/frontend"

    log_ok "Frontend image built:"
    for t in "${FRONTEND_TAGS[@]}"; do echo "         $t"; done
fi

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}  Build complete.${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Next:"
echo "    Push images:    bash scripts/docker/push.sh"
echo "    Deploy compose: bash scripts/docker/deploy-compose.sh"
echo "    Deploy K8s:     bash scripts/docker/deploy-k8s.sh"
echo ""
