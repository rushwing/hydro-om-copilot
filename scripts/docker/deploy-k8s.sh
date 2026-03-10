#!/usr/bin/env bash
# =============================================================================
# Hydro O&M Copilot — Deploy to Kubernetes
#
# Applies manifests from scripts/k8s/ to the target cluster.
# Supports kustomize overlays for multi-env (dev/staging/prod) deployment.
#
# Prerequisites:
#   - kubectl configured with target cluster context
#   - Images pushed to registry (run scripts/docker/push.sh first)
#   - Secret created: kubectl create secret generic hydro-om-secrets ... (see below)
#
# Usage:
#   bash scripts/docker/deploy-k8s.sh apply            # apply all manifests
#   bash scripts/docker/deploy-k8s.sh delete           # remove all resources
#   bash scripts/docker/deploy-k8s.sh status           # show pod/svc status
#   bash scripts/docker/deploy-k8s.sh rollout-status   # wait for rollout
#   bash scripts/docker/deploy-k8s.sh ingest           # run KB ingest Job
#   bash scripts/docker/deploy-k8s.sh logs [pod]       # tail pod logs
#
# Environment variables:
#   KUBE_CONTEXT   kubectl context to use (default: current context)
#   KUBE_NS        K8s namespace (default: hydro-om)
#   IMAGE_TAG      Image tag to deploy (default: latest)
#   REGISTRY       Image registry prefix (required for apply)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
K8S_DIR="$SCRIPT_DIR/../k8s"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()   { echo -e "${GREEN}[ OK ]${NC}  $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_fail() { echo -e "${RED}[FAIL]${NC}  $*"; }

COMMAND="${1:-apply}"
NS="${KUBE_NS:-hydro-om}"
REGISTRY="${REGISTRY:-}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Set kubectl context if specified
KUBECTL_ARGS=()
if [[ -n "${KUBE_CONTEXT:-}" ]]; then
    KUBECTL_ARGS+=(--context "$KUBE_CONTEXT")
fi

KUBECTL="kubectl ${KUBECTL_ARGS[*]:-}"

header() {
    echo ""
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}  Hydro O&M Copilot — K8s $1${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    log_info "Namespace : $NS"
    log_info "Image tag : $IMAGE_TAG"
    log_info "Registry  : ${REGISTRY:-<not set>}"
    echo ""
}

case "$COMMAND" in

    apply)
        header "Apply"

        if [[ -z "$REGISTRY" ]]; then
            log_warn "REGISTRY is not set — manifests will use placeholder image names."
            log_warn "Set REGISTRY=registry.example.com/hydro before running."
        fi

        # ── Step 1: Create/ensure the secret exists ───────────────────────
        if ! $KUBECTL get secret hydro-om-secrets -n "$NS" &>/dev/null 2>&1; then
            log_warn "Secret 'hydro-om-secrets' not found in namespace '$NS'."
            log_warn "Create it before applying:"
            echo ""
            echo "  kubectl create secret generic hydro-om-secrets \\"
            echo "    --namespace $NS \\"
            echo "    --from-literal=ANTHROPIC_API_KEY=<your-key>"
            echo ""
            log_warn "Continuing — backend will fail to start without the secret."
        fi

        # ── Step 2: Substitute image tags and apply manifests ─────────────
        log_info "Applying manifests from $K8S_DIR …"

        # Use kustomize if available; fall back to raw kubectl apply
        if command -v kustomize &>/dev/null; then
            log_info "Using kustomize"
            # Edit image tags in kustomization before applying
            (
                cd "$K8S_DIR"
                kustomize edit set image \
                    "hydro-om-backend=${REGISTRY:+${REGISTRY}/}hydro-om-backend:${IMAGE_TAG}" \
                    "hydro-om-frontend=${REGISTRY:+${REGISTRY}/}hydro-om-frontend:${IMAGE_TAG}" \
                    2>/dev/null || true
            )
            kustomize build "$K8S_DIR" \
                | REGISTRY="$REGISTRY" IMAGE_TAG="$IMAGE_TAG" \
                  envsubst '${REGISTRY} ${IMAGE_TAG}' \
                | $KUBECTL apply -f -
        else
            # Raw apply with envsubst for image substitution
            for manifest in "$K8S_DIR"/[0-9]*.yaml; do
                log_info "Applying $(basename "$manifest") …"
                REGISTRY="$REGISTRY" IMAGE_TAG="$IMAGE_TAG" \
                    envsubst '${REGISTRY} ${IMAGE_TAG}' < "$manifest" \
                    | $KUBECTL apply -f -
            done
        fi

        log_ok "Manifests applied."
        echo ""
        log_info "Wait for rollout: bash $0 rollout-status"
        log_info "Check status:     bash $0 status"
        ;;

    delete)
        header "Delete"
        log_warn "This will remove all hydro-om resources from namespace '$NS'."
        read -r -p "  Confirm? [y/N] " confirm
        if [[ "${confirm,,}" == "y" ]]; then
            for manifest in "$K8S_DIR"/[0-9]*.yaml; do
                $KUBECTL delete -f "$manifest" --ignore-not-found=true || true
            done
            log_ok "Resources deleted."
        else
            log_info "Aborted."
        fi
        ;;

    status)
        echo ""
        echo -e "${BOLD}Pods (namespace: $NS)${NC}"
        $KUBECTL get pods -n "$NS" -o wide
        echo ""
        echo -e "${BOLD}Services${NC}"
        $KUBECTL get svc -n "$NS"
        echo ""
        echo -e "${BOLD}Ingress${NC}"
        $KUBECTL get ingress -n "$NS" 2>/dev/null || echo "  (none)"
        echo ""
        echo -e "${BOLD}PersistentVolumeClaims${NC}"
        $KUBECTL get pvc -n "$NS"
        ;;

    rollout-status)
        log_info "Waiting for rollouts…"
        $KUBECTL rollout status deployment/hydro-om-backend  -n "$NS"
        $KUBECTL rollout status deployment/hydro-om-frontend -n "$NS"
        $KUBECTL rollout status statefulset/qdrant           -n "$NS"
        log_ok "All rollouts complete."
        ;;

    ingest)
        log_info "Creating KB ingestion Job…"
        cat <<EOF | $KUBECTL apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: hydro-om-ingest-$(date +%s)
  namespace: $NS
  labels:
    app.kubernetes.io/name: hydro-om-copilot
    app.kubernetes.io/component: ingest
spec:
  ttlSecondsAfterFinished: 3600
  template:
    spec:
      restartPolicy: OnFailure
      containers:
      - name: ingest
        image: ${REGISTRY:+${REGISTRY}/}hydro-om-backend:${IMAGE_TAG}
        command:
        - python3.11
        - -m
        - scripts.ingest_kb
        - --kb-dir
        - /app/knowledge_base/docs_internal
        envFrom:
        - configMapRef:
            name: hydro-om-config
        - secretRef:
            name: hydro-om-secrets
        volumeMounts:
        - name: knowledge-base
          mountPath: /app/knowledge_base
        - name: models-cache
          mountPath: /app/models
      volumes:
      - name: knowledge-base
        persistentVolumeClaim:
          claimName: hydro-om-knowledge-base
      - name: models-cache
        persistentVolumeClaim:
          claimName: hydro-om-models-cache
EOF
        log_ok "Ingest Job created. Follow logs with: bash $0 logs"
        ;;

    logs)
        POD="${2:-}"
        if [[ -z "$POD" ]]; then
            # Pick the first running backend pod
            POD="$($KUBECTL get pods -n "$NS" \
                    -l app.kubernetes.io/component=backend \
                    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
        fi
        if [[ -z "$POD" ]]; then
            log_warn "No backend pod found. Use: bash $0 logs <pod-name>"
            $KUBECTL get pods -n "$NS"
            exit 1
        fi
        log_info "Following logs for pod: $POD"
        exec $KUBECTL logs -n "$NS" -f "$POD"
        ;;

    *)
        echo "Usage: $0 {apply|delete|status|rollout-status|ingest|logs [pod]}"
        exit 1
        ;;
esac
