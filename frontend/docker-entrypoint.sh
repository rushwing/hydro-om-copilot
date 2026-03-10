#!/bin/sh
# =============================================================================
# Frontend container entrypoint
# Substitutes ${BACKEND_URL} in nginx config at runtime, then starts nginx.
# =============================================================================
set -e

BACKEND_URL="${BACKEND_URL:-http://backend:8000}"
export BACKEND_URL

# Substitute environment variables in the nginx config template
envsubst '${BACKEND_URL}' \
    < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

echo "[entrypoint] BACKEND_URL=${BACKEND_URL}"
echo "[entrypoint] Starting nginx..."

exec nginx -g 'daemon off;'
