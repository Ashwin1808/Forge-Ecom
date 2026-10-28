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

storefront_key="smoke-store-$(date +%s)-$$"
storefront_payload="$(
  "$PYTHON" - "$product_id" <<'PY'
import json, sys
print(json.dumps({
    "customer": {"name": "Storefront Smoke", "email": "storefront-smoke@example.com"},
    "delivery_address": {
        "line1": "1 Market Street",
        "line2": "Suite 200",
        "city": "San Francisco",
        "region": "CA",
        "postal_code": "94105",
        "country": "US",
    },
    "items": [{"product_id": sys.argv[1], "quantity": 1}],
}))
PY
)"

storefront_response="$(
  curl -fsS -X POST "$BASE_URL/api/v1/storefront/checkout" \
    -H "Content-Type: application/json" \
    -H "Idempotency-Key: $storefront_key" \
    --data "$storefront_payload"
)"
storefront_order_id="$("$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$storefront_response")"
storefront_status="$("$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"$storefront_response")"
storefront_payment="$("$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["payment_status"])' <<<"$storefront_response")"
storefront_channel="$("$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["channel"])' <<<"$storefront_response")"

if [ "$storefront_status" != "AWAITING_PAYMENT" ] || [ "$storefront_payment" != "CREATED" ] || [ "$storefront_channel" != "STOREFRONT" ]; then
  echo "Unexpected storefront checkout state: $storefront_response" >&2
  exit 1
fi

storefront_replay="$(
  curl -fsS -X POST "$BASE_URL/api/v1/storefront/checkout" \
    -H "Content-Type: application/json" \
    -H "Idempotency-Key: $storefront_key" \
    --data "$storefront_payload"
)"
storefront_replay_id="$("$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$storefront_replay")"
if [ "$storefront_replay_id" != "$storefront_order_id" ]; then
  echo "Storefront idempotency replay returned a different order." >&2
  exit 1
fi

storefront_detail="$(curl -fsS "$BASE_URL/api/v1/storefront/orders/$storefront_order_id")"
storefront_detail_status="$("$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"$storefront_detail")"
echo "Storefront order $storefront_order_id is $storefront_detail_status (reservation replay verified)."
echo "Smoke test passed."
