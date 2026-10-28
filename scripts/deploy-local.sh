#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."

TAG="${1:-$(git rev-parse --short HEAD)}"
if [[ ! "$TAG" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Invalid image tag: $TAG" >&2
  exit 1
fi

STATE_DIR="${STATE_DIR:-.deploy}"
CURRENT_FILE="$STATE_DIR/current-image-tag"
PREVIOUS_FILE="$STATE_DIR/previous-image-tag"
mkdir -p "$STATE_DIR"

PREVIOUS=""
if [[ -f "$CURRENT_FILE" ]]; then
  PREVIOUS="$(cat "$CURRENT_FILE")"
fi

echo "Building images tagged $TAG ..."
IMAGE_TAG="$TAG" docker compose build

if [[ -n "$PREVIOUS" && "$PREVIOUS" != "$TAG" ]]; then
  printf '%s\n' "$PREVIOUS" > "$PREVIOUS_FILE"
fi
printf '%s\n' "$TAG" > "$CURRENT_FILE"

echo "Deploying $TAG ..."
IMAGE_TAG="$TAG" docker compose up -d --wait --force-recreate \
  order-service inventory-service frontend

if ! ./scripts/smoke-test.sh; then
  echo "Deployment $TAG failed its smoke test." >&2
  if [[ -f "$PREVIOUS_FILE" ]]; then
    echo "Rolling back to $(cat "$PREVIOUS_FILE") ..." >&2
    ./scripts/rollback-local.sh
  else
    echo "No previous image tag is recorded; manual recovery is required." >&2
  fi
  exit 1
fi

echo "Deployment $TAG is healthy. Storefront: http://localhost:8080/store"
