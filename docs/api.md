# API Reference

## Base URLs

- Browser and normal integration path: `http://localhost:8080`
- Direct Order Service: `http://localhost:8000`
- Inventory Service: internal only (`http://inventory-service:8001` inside Compose)

The frontend uses the same-origin nginx proxy for `/api/*` and `/health`. The Order Service is also published on loopback for direct API calls and metrics.

## Common Behavior

### Request IDs

Clients may send `X-Request-ID` matching `^[A-Za-z0-9._-]{8,128}$`. Otherwise the service generates a 32-character hex ID. The effective ID is returned in the `X-Request-ID` response header and in error bodies.

### Error shape

```json
{
  "error": {
    "code": "insufficient_stock",
    "message": "One or more products do not have enough stock.",
    "details": {
      "shortages": [
        {
          "product_id": "11111111-1111-4111-8111-111111111111",
          "requested": 5,
          "available": 2
        }
      ]
    }
  },
  "request_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
}
```

Validation errors use `code: "validation_error"` and a sanitized `details` array containing location, message, and type. Untrusted input is not echoed.

### Limits

- Request body: 128 KiB by default for write methods.
- API rate limit: 120 requests per minute per client by default, applied to `/api/*`.
- Rate-limited responses are `429` with `Retry-After`.
- Successful rate-limited responses include `X-RateLimit-Limit` and `X-RateLimit-Remaining`.

### Security headers

API responses include `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and `Cache-Control: no-store`. nginx adds its own header and CSP policy for the SPA.

## System Endpoints

### `GET /health`

Order Service:

```json
{
  "status": "ok",
  "service": "order-service",
  "version": "0.1.0",
  "environment": "local"
}
```

### `GET /ready`

Checks database connectivity.

```json
{"status": "ready", "checks": {"database": "ok"}}
```

Returns `503` when the database is unavailable.

### `GET /metrics`

Prometheus text exposition. Available on the Order Service at `http://localhost:8000/metrics`. The Inventory Service endpoint is internal. Metrics are not proxied by nginx.

## Catalog (Order Service Proxy)

### `GET /api/v1/products`

Query parameters:

| Name | Type | Default | Constraints |
| --- | --- | --- | --- |
| `page` | integer | `1` | `>= 1` |
| `page_size` | integer | `20` | `1..100` |

Response:

```json
{
  "items": [
    {
      "id": "11111111-1111-4111-8111-111111111111",
      "sku": "KEY-001",
      "name": "Forge Mechanical Keyboard",
      "description": "Hot-swappable 75% keyboard with tactile switches.",
      "price_cents": 14900,
      "currency": "USD",
      "quantity_available": 42,
      "quantity_reserved": 0,
      "in_stock": true,
      "created_at": "2026-10-28T10:49:46.000000Z"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 6
}
```

### `GET /api/v1/products/{product_id}`

Returns one product. `404 product_not_found` when missing. `503 catalog_unavailable` when the Inventory Service is unavailable.

## Orders

### `POST /api/v1/orders`

Creates an order and synchronously reserves inventory.

Required header:

```text
Idempotency-Key: <8..128 chars, [A-Za-z0-9._:-]>
```

Request:

```json
{
  "customer": {
    "name": "Ada Lovelace",
    "email": "ada@example.com"
  },
  "items": [
    {"product_id": "11111111-1111-4111-8111-111111111111", "quantity": 2}
  ]
}
```

Constraints:

- Customer name: 1–120 characters after trimming.
- Valid email address; normalized to lowercase.
- 1–50 line items.
- Quantity: 1–100 per line.
- Product IDs must be unique within the request.

Response `201`:

```json
{
  "id": "33333333-3333-4333-8333-333333333333",
  "status": "CONFIRMED",
  "payment_status": null,
  "channel": "OPS",
  "customer": {"name": "Ada Lovelace", "email": "ada@example.com"},
  "delivery_address": null,
  "items": [
    {
      "product_id": "11111111-1111-4111-8111-111111111111",
      "sku": "KEY-001",
      "name": "Forge Mechanical Keyboard",
      "quantity": 2,
      "unit_price_cents": 14900,
      "currency": "USD",
      "line_total_cents": 29800
    }
  ],
  "total_cents": 29800,
  "currency": "USD",
  "reservation_expires_at": null,
  "failure_code": null,
  "failure_message": null,
  "created_at": "2026-10-28T10:50:05.000000Z",
  "updated_at": "2026-10-28T10:50:05.100000Z"
}
```

Idempotent replay:

- Same key and same payload returns `201` with the original order.
- A `FAILED` order replay returns its original failure status and details.
- A `PENDING` order replay returns `409 order_in_progress` and `Retry-After: 2`.
- Same key and a different payload returns `409 idempotency_conflict`.

Failure responses retain an `order_id` in `error.details`:

| Status | Code | Meaning |
| --- | --- | --- |
| `409` | `inventory_insufficient_stock` | Reservation rejected; order retained as `FAILED` |
| `409` | `idempotency_conflict` | Key reused with a different payload |
| `409` | `order_in_progress` | Original order is still `PENDING` |
| `422` | `inventory_unknown_product` | Product missing/inactive; order retained as `FAILED` |
| `422` | `validation_error` | Request validation failed |
| `502` | `inventory_protocol` | Inventory response did not match the order |
| `503` | `inventory_unavailable` | Inventory Service unreachable |
| `504` | `inventory_timeout` | Inventory Service timed out |

Example failure:

```json
{
  "error": {
    "code": "inventory_insufficient_stock",
    "message": "One or more products do not have enough stock.",
    "details": {"order_id": "33333333-3333-4333-8333-333333333333"}
  },
  "request_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
}
```

### `GET /api/v1/orders`

Query parameters:

| Name | Type | Default | Notes |
| --- | --- | --- | --- |
| `page` | integer | `1` | `>= 1` |
| `page_size` | integer | `20` | `1..100` |
| `status` | enum | none | `PENDING`, `AWAITING_PAYMENT`, `CONFIRMED`, `EXPIRED`, or `FAILED` |

Response shape matches the catalog list shape with `Order` objects and a `total`.

### `GET /api/v1/orders/{order_id}`

Returns one order, including items. `404 order_not_found` when missing.

### `GET /api/v1/orders/{order_id}/items`

Returns `{"items": [...]}` for the order. `404 order_not_found` when missing.

## Storefront

### `POST /api/v1/storefront/checkout`

Creates a storefront order and synchronously reserves inventory. The order stops at `AWAITING_PAYMENT`; no payment is collected in this phase.

Required header:

```text
Idempotency-Key: <8..128 chars, [A-Za-z0-9._:-]>
```

Request:

```json
{
  "customer": {
    "name": "Grace Hopper",
    "email": "grace@example.com"
  },
  "delivery_address": {
    "line1": "1 Market Street",
    "line2": "Suite 200",
    "city": "San Francisco",
    "region": "CA",
    "postal_code": "94105",
    "country": "US"
  },
  "items": [
    {"product_id": "11111111-1111-4111-8111-111111111111", "quantity": 2}
  ]
}
```

Constraints:

- Customer name: 1–120 characters after trimming.
- Valid email address; normalized to lowercase.
- Address line 1: 1–200 characters; city: 1–120; postal code: 1–32; country: 2–80.
- Optional line 2 and region are trimmed and stored as `null` when blank.
- 1–50 line items; quantity 1–100; product IDs unique.
- Prices, stock, and totals are recalculated by the server.

Response `201`:

```json
{
  "id": "44444444-4444-4444-8444-444444444444",
  "status": "AWAITING_PAYMENT",
  "payment_status": "CREATED",
  "channel": "STOREFRONT",
  "customer": {"name": "Grace Hopper", "email": "grace@example.com"},
  "delivery_address": {
    "line1": "1 Market Street",
    "line2": "Suite 200",
    "city": "San Francisco",
    "region": "CA",
    "postal_code": "94105",
    "country": "US"
  },
  "items": [
    {
      "product_id": "11111111-1111-4111-8111-111111111111",
      "sku": "KEY-001",
      "name": "Forge Mechanical Keyboard",
      "quantity": 2,
      "unit_price_cents": 14900,
      "currency": "USD",
      "line_total_cents": 29800
    }
  ],
  "total_cents": 29800,
  "currency": "USD",
  "reservation_expires_at": "2026-10-28T16:00:00.000000Z",
  "failure_code": null,
  "failure_message": null,
  "created_at": "2026-10-28T15:45:00.000000Z",
  "updated_at": "2026-10-28T15:45:00.010000Z"
}
```

Replay behavior:

- Same key and same payload returns the original `AWAITING_PAYMENT` or `CONFIRMED` order.
- An `EXPIRED` order returns `409 checkout_expired` with `order_id`.
- A `FAILED` order returns its original failure.
- A `PENDING` order returns `409 checkout_in_progress` and `Retry-After: 2`.
- Same key with a different customer, address, or items returns `409 idempotency_conflict`.

Failure responses use the same inventory codes as operations orders and retain `order_id` in `error.details`:

| Status | Code | Meaning |
| --- | --- | --- |
| `409` | `inventory_insufficient_stock` | Reservation rejected; checkout retained as `FAILED` |
| `409` | `checkout_expired` | Reservation expired; start a new checkout |
| `409` | `checkout_in_progress` | Original checkout is still `PENDING` |
| `409` | `idempotency_conflict` | Key reused with a different checkout payload |
| `422` | `inventory_unknown_product` | Product missing/inactive; checkout retained as `FAILED` |
| `422` | `validation_error` | Request validation failed |
| `502` | `inventory_protocol` | Inventory response did not match the checkout |
| `503` | `inventory_unavailable` | Inventory Service unreachable |
| `504` | `inventory_timeout` | Inventory Service timed out |

The default reservation TTL is 900 seconds. A background worker releases expired reservations and changes the order to `EXPIRED` with `failure_code=reservation_expired`.

### `GET /api/v1/storefront/orders/{order_id}`

Returns one storefront order, including the delivery address and payment status. Operations-channel orders are hidden and return `404 order_not_found`.

## Internal Inventory API

These endpoints are reachable only inside the Compose network. They are documented for operations, seeding, and tests. They are not exposed through nginx.

### `GET /api/v1/products`

Same pagination behavior as the Order Service proxy. Returns live inventory quantities.

### `POST /api/v1/products`

Creates a product and its inventory row.

```json
{
  "sku": "KEY-001",
  "name": "Forge Mechanical Keyboard",
  "description": "Hot-swappable 75% keyboard with tactile switches.",
  "price_cents": 14900,
  "currency": "USD",
  "initial_quantity": 42
}
```

Validation highlights:

- SKU: 2–64 characters, uppercase letters/digits/hyphens, normalized to uppercase.
- Name: 1–200 characters.
- Price: 1–100,000,000 cents.
- Initial quantity: 0–1,000,000.
- Currency must match the service's configured store currency.
- Duplicate SKU returns `409 product_sku_conflict`.

### `POST /api/v1/inventory/reservations`

Internal reservation operation. The Order Service calls this with `reservation_id` equal to the order UUID.

```json
{
  "reservation_id": "33333333-3333-4333-8333-333333333333",
  "items": [
    {"product_id": "11111111-1111-4111-8111-111111111111", "quantity": 2}
  ]
}
```

Responses:

- `201` — new reservation created.
- `200` — idempotent replay with the stored snapshot.
- `409 insufficient_stock` — details contain shortages.
- `404 unknown_product` — details contain missing/inactive product IDs.
- `409 idempotency_conflict` — same reservation ID with a different payload.

### `GET /api/v1/inventory/reservations/{reservation_id}`

Returns the stored reservation snapshot or `404 reservation_not_found`.

### `POST /api/v1/inventory/reservations/{reservation_id}/release`

Releases a reservation, restoring available stock and clearing reserved stock. The operation is idempotent.

- `200` — reservation is `RELEASED` (including replay).
- `404 reservation_not_found` — no reservation with that ID exists.

The Order Service expiry worker calls this endpoint. It is internal and is not proxied by nginx.

## Examples

Get a product ID and create an order through nginx:

```bash
PRODUCT_ID="$(
  curl -sS http://localhost:8080/api/v1/products?page_size=1 |
    python3 -c 'import json,sys; print(json.load(sys.stdin)["items"][0]["id"])'
)"

curl -sS http://localhost:8080/api/v1/orders \
  -H 'Content-Type: application/json' \
  -H "Idempotency-Key: example-$(date +%s)" \
  -d "{
    \"customer\": {\"name\": \"Ada Lovelace\", \"email\": \"ada@example.com\"},
    \"items\": [{\"product_id\": \"$PRODUCT_ID\", \"quantity\": 1}]
  }"
```

Replay the same key and payload to verify idempotency. Reusing the key with a different quantity returns `409 idempotency_conflict`.
