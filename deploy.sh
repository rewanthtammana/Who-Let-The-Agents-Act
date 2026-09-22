#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

fail() {
    echo "deploy.sh: $1" >&2
    exit 1
}

command -v docker >/dev/null 2>&1 || fail "Docker is not installed. Install Docker Engine and the Compose plugin first."
docker compose version >/dev/null 2>&1 || fail "Docker Compose is not available. Install the Docker Compose plugin first."
[[ -f .env ]] || fail "Missing .env. Copy .env.example to .env and set the production values."

set -a
# shellcheck disable=SC1091
. ./.env
set +a

[[ -n "${DOMAIN:-}" && "$DOMAIN" != "example.com" ]] || fail "Set DOMAIN to the real DNS name in .env."
if [[ -z "${GROQ_API_KEYS:-}" && -z "${GROQ_API_KEY:-}" ]]; then
    fail "Set GROQ_API_KEYS (comma-separated) or GROQ_API_KEY in .env."
fi
[[ "${GROQ_API_KEYS:-}" != "replace-me-key-1,replace-me-key-2" && "${GROQ_API_KEY:-}" != "replace-me" ]] || fail "Set real Groq API key values in .env."

if [[ "${COOKIE_SECURE:-0}" != "1" ]]; then
    fail "Set COOKIE_SECURE=1 because Caddy serves the application over HTTPS."
fi

# Compose enables source watching for local development by default. Never run
# the production service with a development reloader.
export RELOAD=false

echo "Validating Compose configuration..."
docker compose config -q
echo "Ensuring persistent Caddy volumes exist..."
docker volume create who-let-the-agents-act_caddy_data >/dev/null
docker volume create who-let-the-agents-act_caddy_config >/dev/null
echo "Removing existing application containers..."
docker compose down --remove-orphans

echo "Building and starting Who Let the Agents Act with Caddy..."
docker compose up -d --build --remove-orphans


echo "Waiting for the application health check..."
for attempt in {1..30}; do
    if curl -fsS --max-time 3 http://127.0.0.1:${APP_PORT:-8000}/api/health >/dev/null; then
        echo "Who Let the Agents Act is healthy."
        break
    fi
    if [[ "$attempt" == 30 ]]; then
        docker compose ps
        docker compose logs --tail=80 who-let-the-agents-act caddy
        fail "The application did not become healthy."
    fi
    sleep 2
done

echo
echo "Deployment complete."
echo "Application: https://${DOMAIN}"
echo "Check status: docker compose ps"
