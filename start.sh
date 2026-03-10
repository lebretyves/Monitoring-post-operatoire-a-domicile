#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

ENV_FILE="$PROJECT_ROOT/.env"
ENV_EXAMPLE_FILE="$PROJECT_ROOT/.env.example"
RUNTIME_DIR="$PROJECT_ROOT/runtime"
mkdir -p "$RUNTIME_DIR"

SIMULATOR_PID=""
BRIDGE_PID=""
FRONTEND_PID=""
CLEANUP_STARTED=0

log() {
  printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

docker_compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command_exists docker-compose; then
    docker-compose "$@"
  else
    log "ERROR: Docker Compose is not installed"
    exit 1
  fi
}

cleanup() {
  local exit_code="${1:-0}"
  if [[ "$CLEANUP_STARTED" -eq 1 ]]; then
    return
  fi
  CLEANUP_STARTED=1

  log "Stopping services"

  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
    wait "$FRONTEND_PID" 2>/dev/null || true
  fi

  if [[ -n "$BRIDGE_PID" ]] && kill -0 "$BRIDGE_PID" >/dev/null 2>&1; then
    kill "$BRIDGE_PID" >/dev/null 2>&1 || true
    wait "$BRIDGE_PID" 2>/dev/null || true
  fi

  if [[ -n "$SIMULATOR_PID" ]] && kill -0 "$SIMULATOR_PID" >/dev/null 2>&1; then
    kill "$SIMULATOR_PID" >/dev/null 2>&1 || true
    wait "$SIMULATOR_PID" 2>/dev/null || true
  fi

  if command_exists docker; then
    docker_compose down >/dev/null 2>&1 || true
  fi

  exit "$exit_code"
}

trap 'cleanup 130' INT TERM
trap 'cleanup 1' ERR

ensure_env_file() {
  if [[ -f "$ENV_FILE" ]]; then
    return
  fi

  if [[ ! -f "$ENV_EXAMPLE_FILE" ]]; then
    log "ERROR: .env.example is missing"
    exit 1
  fi

  cp "$ENV_EXAMPLE_FILE" "$ENV_FILE"
}

load_env() {
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
}

wait_for_http() {
  local url="$1"

  while true; do
    if command_exists curl && curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
}

open_url() {
  local url="$1"
  if command_exists open; then
    open "$url" >/dev/null 2>&1 || true
  fi
}

ensure_docker_ready() {
  if ! command_exists docker; then
    log "ERROR: Docker CLI is not installed"
    exit 1
  fi

  if docker info >/dev/null 2>&1; then
    log "Docker ready"
    return
  fi

  if [[ "$(uname -s)" == "Darwin" ]]; then
    log "Starting Docker Desktop"
    open -a Docker >/dev/null 2>&1 || true
  else
    log "Docker is not running"
  fi

  while ! docker info >/dev/null 2>&1; do
    log "Waiting for Docker..."
    sleep 2
  done

  log "Docker ready"
}

start_simulator() {
  if [[ -f "$PROJECT_ROOT/simulator/simulator.py" ]]; then
    log "Starting simulator"
    (
      cd "$PROJECT_ROOT/simulator"
      exec python3 simulator.py
    ) >"$RUNTIME_DIR/simulator.log" 2>&1 &
    SIMULATOR_PID="$!"
    return
  fi

  if [[ -f "$PROJECT_ROOT/services/simulator/app/main.py" ]]; then
    log "Starting simulator"
    return
  fi

  log "Starting simulator"
}

start_bridge_server() {
  if [[ -f "$PROJECT_ROOT/bridge-server/package.json" ]]; then
    log "Starting backend"
    (
      cd "$PROJECT_ROOT/bridge-server"
      if [[ -f package-lock.json ]]; then
        npm ci
      else
        npm install
      fi

      if npm run | grep -qE '^[[:space:]]+dev'; then
        exec npm run dev
      elif npm run | grep -qE '^[[:space:]]+start'; then
        exec npm start
      else
        exec node server.js
      fi
    ) >"$RUNTIME_DIR/bridge-server.log" 2>&1 &
    BRIDGE_PID="$!"
    return
  fi

  if [[ -f "$PROJECT_ROOT/services/backend/Dockerfile" ]]; then
    log "Starting backend"
    return
  fi

  log "Starting backend"
}

start_frontend() {
  if [[ -f "$PROJECT_ROOT/webapp/package.json" ]]; then
    log "Starting frontend"
    (
      cd "$PROJECT_ROOT/webapp"
      if [[ -f package-lock.json ]]; then
        npm ci
      else
        npm install
      fi
      exec npm start
    ) >"$RUNTIME_DIR/frontend.log" 2>&1 &
    FRONTEND_PID="$!"
    return
  fi

  if [[ -f "$PROJECT_ROOT/services/frontend/package.json" ]]; then
    log "Starting frontend"
    return
  fi

  log "Starting frontend"
}

main() {
  log "Starting platform"

  ensure_env_file
  load_env
  ensure_docker_ready

  log "Starting containers"
  docker_compose up -d

  start_simulator
  start_bridge_server
  start_frontend

  local frontend_port="${FRONTEND_PORT:-5173}"
  wait_for_http "http://localhost:${frontend_port}"
  open_url "http://localhost:${frontend_port}"

  log "Platform ready"

  while true; do
    sleep 1
  done
}

main "$@"