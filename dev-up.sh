#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
COMPOSE_FILE="$ROOT_DIR/docker-compose.full.yml"
SERVICES="${*:-api web}"

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "No se encontro docker-compose.full.yml en $ROOT_DIR"
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
else
  echo "Docker Compose no esta instalado."
  exit 1
fi

echo "Levantando servicios: $SERVICES"
sh -c "$COMPOSE_CMD -f '$COMPOSE_FILE' up -d --build $SERVICES"

echo "Listo: http://localhost:5173"
