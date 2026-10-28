#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."

STATE_DIR="${STATE_DIR:-.deploy}"
CURRENT_FILE="$STATE_DIR/current-image-tag"
PREVIOUS_FILE="$STATE_DIR/previous-image-tag"

if [[ ! -f "$PREVIOUS_FILE" ]]; then
  echo "No previous image tag recorded in $PREVIOUS_FILE." >&2
  echo "Deploy at least two tags before rolling back." >&2
  exit 1
fi

PREVIOUS="$(cat "$PREVIOUS_FILE")"
CURRENT=""
if [[ -f "$CURRENT_FILE" ]]; then
  CURRENT="$(cat "$CURRENT_FILE")"
fi

echo "Rolling back to image tag $PREVIOUS ..."
IMAGE_TAG="$PREVIOUS" docker compose up -d --wait --force-recreate \
  order-service inventory-service frontend

if ! ./scripts/smoke-test.sh; then
  echo "Rollback to $PREVIOUS failed its smoke test." >&2
  exit 1
fi

printf '%s\n' "$PREVIOUS" > "$CURRENT_FILE"
if [[ -n "$CURRENT" ]]; then
  printf '%s\n' "$CURRENT" > "$PREVIOUS_FILE"
fi

echo "Rollback to $PREVIOUS is healthy. Storefront: http://localhost:8080/store"
