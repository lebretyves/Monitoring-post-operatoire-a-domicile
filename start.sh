#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_URL="http://localhost:5173"
BACKEND_URL="http://localhost:8000/health"
BACKEND_DOCS_URL="http://localhost:8000/docs"
ENV_FILE="$PROJECT_ROOT/.env"
ENV_EXAMPLE_FILE="$PROJECT_ROOT/.env.example"

DOCKER_TIMEOUT_SECONDS="${DOCKER_TIMEOUT_SECONDS:-180}"
SERVICE_TIMEOUT_SECONDS="${SERVICE_TIMEOUT_SECONDS:-180}"
NO_BROWSER="${NO_BROWSER:-0}"
OPEN_DOCS="${OPEN_DOCS:-0}"

step() {
  echo "==> $1"
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

wait_http_ready() {
  local url="$1"
  local timeout="$2"
  local start_ts
  start_ts="$(date +%s)"

  while true; do
    if has_cmd curl; then
      if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
        return 0
      fi
    elif has_cmd wget; then
      if wget -q --spider --timeout=5 "$url"; then
        return 0
      fi
    else
      echo "Ni curl ni wget n'est disponible pour tester HTTP."
      return 1
    fi

    local now
    now="$(date +%s)"
    if (( now - start_ts >= timeout )); then
      return 1
    fi
    sleep 3
  done
}

ensure_env_file() {
  if [[ -f "$ENV_FILE" ]]; then
    step ".env deja present"
    return
  fi
  if [[ ! -f "$ENV_EXAMPLE_FILE" ]]; then
    echo ".env.example introuvable dans le projet."
    exit 1
  fi
  cp "$ENV_EXAMPLE_FILE" "$ENV_FILE"
  step ".env cree depuis .env.example"
}

show_failure_context() {
  echo
  echo "Etat courant Docker Compose:"
  docker compose ps || true
  echo
  echo "Derniers logs utiles:"
  docker compose logs --tail=80 backend frontend simulator || true
}

open_browser() {
  local url="$1"
  if has_cmd xdg-open; then
    xdg-open "$url" >/dev/null 2>&1 || true
  elif has_cmd open; then
    open "$url" >/dev/null 2>&1 || true
  fi
}

main() {
  cd "$PROJECT_ROOT"

  if ! has_cmd docker; then
    echo "La commande docker est introuvable."
    exit 1
  fi

  step "Preparation du projet"
  ensure_env_file

  step "Validation Docker Compose"
  docker compose config >/dev/null

  step "Construction et demarrage de la stack"
  docker compose up --build -d

  step "Attente du backend"
  if ! wait_http_ready "$BACKEND_URL" "$SERVICE_TIMEOUT_SECONDS"; then
    show_failure_context
    echo "Le backend ne repond pas sur $BACKEND_URL"
    exit 1
  fi

  step "Attente du frontend"
  if ! wait_http_ready "$FRONTEND_URL" "$SERVICE_TIMEOUT_SECONDS"; then
    show_failure_context
    echo "Le frontend ne repond pas sur $FRONTEND_URL"
    exit 1
  fi

  echo
  echo "Stack prete"
  echo "- Frontend : $FRONTEND_URL"
  echo "- Backend  : http://localhost:8000"
  echo "- Docs API : $BACKEND_DOCS_URL"
  echo
  echo "Pour suivre les logs : docker compose logs -f --tail=200"
  echo "Pour arreter : docker compose down -v"

  if [[ "$NO_BROWSER" != "1" ]]; then
    step "Ouverture du dashboard"
    open_browser "$FRONTEND_URL"
    if [[ "$OPEN_DOCS" == "1" ]]; then
      open_browser "$BACKEND_DOCS_URL"
    fi
  fi
}

main "$@"
