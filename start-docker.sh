#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
COMPOSE_FILE="$ROOT_DIR/docker-compose.full.yml"

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

echo "Levantando OSIRIS (api + web + postgres + redis)..."
sh -c "$COMPOSE_CMD -f '$COMPOSE_FILE' up -d --build"

echo
echo "Listo."
echo "Frontend: http://localhost:5173"
echo "API:      http://localhost:8000"
echo "Docs API: http://localhost:8000/docs"
