#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."
docker compose exec -T inventory-service python -m inventory_service.seed
