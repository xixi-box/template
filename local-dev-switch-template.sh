#!/usr/bin/env bash

# Local development switch script template.
# - Exports default environment variables only when they are not already set.
# - Removes project containers that may occupy local development ports.
# - Starts the local Docker Compose services needed by the project.

if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi

set -Eeuo pipefail

PROJECT_NAME="example-project"
PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"

log() {
  printf '\n==> %s\n' "$1"
}

die() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

ensure_env() {
  name="$1"
  default_value="$2"
  if [ -z "${!name:-}" ]; then
    export "$name=$default_value"
    printf 'Set default %s=%s\n' "$name" "$default_value"
  else
    printf 'Keep existing %s\n' "$name"
  fi
}

docker_compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    die "Docker Compose is not available. Install docker compose plugin or docker-compose."
  fi
}

remove_container_if_exists() {
  name="$1"
  if docker container inspect "$name" >/dev/null 2>&1; then
    printf 'Removing container: %s\n' "$name"
    docker stop -t 10 "$name" >/dev/null 2>&1 || true
    docker rm -f "$name" >/dev/null 2>&1 || true
  fi
}

command -v docker >/dev/null 2>&1 || die "Docker is not installed or not in PATH."
[ -f "$COMPOSE_FILE" ] || die "Missing compose file: $COMPOSE_FILE"

log "Load local development defaults"
ensure_env EXAMPLE_MYSQL_ROOT_PASSWORD "local-root-password"
ensure_env EXAMPLE_MYSQL_PASSWORD "local-password"

log "Remove conflicting containers"
for container in \
  example-project-mysql \
  example-project-redis
do
  remove_container_if_exists "$container"
done

log "Start local Docker services"
cd "$PROJECT_ROOT"
docker_compose -f "$COMPOSE_FILE" up -d

log "Running project containers"
docker ps --filter "name=$PROJECT_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
