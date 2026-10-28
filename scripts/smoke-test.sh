#!/usr/bin/env bash
set -Eeuo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
PYTHON="${PYTHON:-python3}"

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Required command not found: $1" >&2
    exit 1
  }
}

require curl
require "$PYTHON"

echo "Waiting for $BASE_URL/health ..."
for attempt in $(seq 1 30); do
  if curl -fsS "$BASE_URL/health" >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" -eq 30 ]; then
    echo "Stack did not become healthy in time." >&2
    exit 1
  fi
  sleep 2
done

health="$(curl -fsS "$BASE_URL/health")"
echo "Health: $health"

products="$(curl -fsS "$BASE_URL/api/v1/products?page_size=100")"
selection="$(
  printf '%s' "$products" | "$PYTHON" -c '
import json, sys
payload = json.load(sys.stdin)
for product in payload["items"]:
    if product["quantity_available"] > 0:
        print(product["id"], product["sku"], product["name"])
        break
else:
    raise SystemExit("No product with available stock")
'
)"
read -r product_id sku product_name <<<"$selection"
echo "Selected product: $sku $product_name"

idempotency_key="smoke-$(date +%s)-$$"
payload="$(
  "$PYTHON" - "$product_id" <<'PY'
import json, sys
print(json.dumps({
    "customer": {"name": "Smoke Test", "email": "smoke@example.com"},
    "items": [{"product_id": sys.argv[1], "quantity": 1}],
}))
PY
)"

response="$(
  curl -fsS -X POST "$BASE_URL/api/v1/orders" \
    -H "Content-Type: application/json" \
    -H "Idempotency-Key: $idempotency_key" \
    --data "$payload"
)"
order_id="$("$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$response")"
status="$("$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"$response")"

if [ "$status" != "CONFIRMED" ]; then
  echo "Expected CONFIRMED order, got $status: $response" >&2
  exit 1
fi

replay="$(
  curl -fsS -X POST "$BASE_URL/api/v1/orders" \
    -H "Content-Type: application/json" \
    -H "Idempotency-Key: $idempotency_key" \
    --data "$payload"
)"
replay_id="$("$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$replay")"
if [ "$replay_id" != "$order_id" ]; then
  echo "Idempotency replay returned a different order." >&2
  exit 1
fi

detail="$(curl -fsS "$BASE_URL/api/v1/orders/$order_id")"
detail_status="$("$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"$detail")"
echo "Order $order_id is $detail_status (idempotent replay verified)."
echo "Smoke test passed."
