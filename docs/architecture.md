# Architecture

## Goals

Forge Commerce is a local workload for practicing DevSecOps end to end. The design favors:

- A real browser-facing application, not a synthetic demo endpoint.
- Exactly two backend microservices with a clear ownership boundary.
- Synchronous inventory reservation with explicit failure behavior.
- Local reproducibility on Apple Silicon without cloud accounts.
- Automated tests that exercise concurrency and cross-service behavior.
- Container images and runtime settings that can later be scanned, signed, and deployed by a pipeline.

It is not designed for production scale, multi-region deployment, or untrusted public exposure.

## System Context

```mermaid
flowchart LR
    U[Browser] -->|HTTP :8080| N[nginx unprivileged]
    N -->|static files| U
    N -->|/api/* /health| O[Order Service :8000]
    O -->|SQL| OD[(forge_orders)]
    O -->|HTTP internal| I[Inventory Service :8001]
    I -->|SQL| ID[(forge_inventory)]

    T[Test runner] -->|ASGI / HTTP| O
    T -->|ASGI / HTTP| I
    T -->|SQL :55433| TD[(test databases)]
```

Published host ports:

- `127.0.0.1:8080` — frontend/nginx
- `127.0.0.1:8000` — Order Service direct API and metrics
- `127.0.0.1:55433` — test PostgreSQL only, behind the `test` profile

Not published:

- Inventory Service `8001`
- Application PostgreSQL `5432`

## Service Responsibilities

### Frontend

- React SPA with a dashboard, order list, order detail, new-order form, and inventory view.
- Talks only to same-origin `/api/v1/*` and `/health`.
- Displays `PENDING`, `CONFIRMED`, and `FAILED` states explicitly.
- Keeps an `Idempotency-Key` stable across retries of the same order form submission.
- Does not own business state; the Order Service is authoritative.

### Order Service

Owns:

- Order records, order items, and commercial totals.
- Idempotency records for order creation.
- The public API surface consumed by the browser.
- The product catalog proxy to the Inventory Service.
- The order workflow and its failure classification.
- Order metrics and request context.

Does not own:

- Product stock.
- Reservation records.
- Inventory pricing data beyond the confirmed snapshot.

### Inventory Service

Owns:

- Products and their active state.
- Available and reserved quantities.
- Reservation records and reservation line snapshots.
- Atomic stock reservation.
- The internal product creation endpoint used for seeding/testing.

Does not own:

- Customer details.
- Order lifecycle.
- Public API exposure.

### PostgreSQL

Two logical databases on one local cluster:

- `forge_orders` owned by `forge_order`
- `forge_inventory` owned by `forge_inventory`

There are no cross-database foreign keys. The services integrate over HTTP, preserving service ownership. Test databases `forge_orders_test` and `forge_inventory_test` are owned by the PostgreSQL bootstrap user for test setup and teardown.

## Data Model

### Order database

`orders`

- UUID primary key.
- `status` in `PENDING`, `CONFIRMED`, `FAILED`.
- Customer name/email snapshot.
- Currency, nullable total, nullable failure code/message.
- Created/updated timestamps.
- Indexes for status/created time and created time.
- Checks for valid status and non-negative total.

`order_items`

- UUID primary key.
- FK to `orders` with cascade delete.
- `product_id` is an external identifier, not a cross-database FK.
- Quantity is positive.
- SKU, product name, unit price, currency, and line total are nullable while pending.
- Unique `(order_id, product_id)` and non-negative price check.

`idempotency_records`

- Client key is the primary key.
- SHA-256 request fingerprint.
- Unique FK to the order.
- Created timestamp.

### Inventory database

`products`

- UUID primary key.
- Unique SKU, name, description, price, currency, active flag.
- Created timestamp.

`inventory`

- One row per product, primary key/FK `product_id`.
- `quantity_available` and `quantity_reserved`.
- Check constraints keep both non-negative.

`inventory_reservations`

- Reservation UUID supplied by the Order Service (equal to the order ID).
- Request fingerprint.
- Status (`RESERVED`).
- Created timestamp.

`inventory_reservation_items`

- FK to reservation and product.
- Quantity, unit price, currency snapshot.
- Unique reservation/product pair.

## Order Creation Workflow

```mermaid
sequenceDiagram
    participant B as Browser
    participant O as Order Service
    participant OD as Order DB
    participant I as Inventory Service
    participant ID as Inventory DB

    B->>O: POST /api/v1/orders + Idempotency-Key
    O->>OD: Look up idempotency key
    alt key exists, same payload
        O-->>B: Replay original order or failure
    else new key
        O->>OD: Insert PENDING order + idempotency record
        O->>I: POST reservation (reservation_id = order.id)
        I->>ID: Lock inventory rows FOR UPDATE
        alt enough stock
            I->>ID: Decrement available, increment reserved, insert reservation
            I-->>O: 201 reservation snapshot
            O->>OD: Lock order, validate reservation, store snapshot + total
            O-->>B: 201 CONFIRMED
        else insufficient stock
            I->>ID: Roll back
            I-->>O: 409 insufficient_stock
            O->>OD: Mark order FAILED
            O-->>B: 409 failure + order_id
        else timeout/unavailable
            O->>OD: Mark order FAILED
            O-->>B: 503/504 failure + order_id
        end
    end
```

The frontend does not create orders directly against the Inventory Service. The Order Service always initiates reservation with the order UUID, which provides a natural idempotency key across the boundary.

## Idempotency and Concurrency

### Order creation

- `Idempotency-Key` is required and validated by FastAPI.
- The request payload is canonicalized: items sorted by product ID, JSON sorted keys, compact separators, SHA-256 hash.
- Same key + same fingerprint:
  - `CONFIRMED` returns the order.
  - `FAILED` returns the original failure and order ID.
  - `PENDING` returns `409 order_in_progress` with `Retry-After: 2`.
- Same key + different fingerprint returns `409 idempotency_conflict`.
- Concurrent first submissions race on the primary key; the loser re-reads the winner and replays it.

### Inventory reservation

- The reservation ID is the order UUID.
- The request fingerprint is canonicalized the same way.
- An existing reservation with the same fingerprint returns `200` with the stored snapshot.
- An existing reservation with a different fingerprint returns `409`.
- Inventory rows are selected in product-ID order with `SELECT ... FOR UPDATE`.
- Shortages are computed before any mutation. On failure, the transaction rolls back.
- Unique constraints and check constraints provide a final database-level guard.

### Why this is enough for the exercise

The workload demonstrates database-enforced idempotency and row-level concurrency control without introducing a message broker, outbox, or saga framework. The remaining gaps are explicit and documented rather than hidden.

## Failure Semantics

| Condition | Order state | HTTP result | Inventory effect |
| --- | --- | --- | --- |
| New order, stock available | `CONFIRMED` | `201` | Stock moved from available to reserved |
| Insufficient stock | `FAILED` | `409` | Transaction rolled back |
| Unknown/inactive product | `FAILED` | `422` | Transaction rolled back |
| Inventory timeout | `FAILED` | `504` | Unknown; the reservation may have committed |
| Inventory unavailable | `FAILED` | `503` | No reservation |
| Inventory protocol mismatch | `FAILED` | `502` | Reservation may exist; needs reconciliation |
| Order process crash before finalization | `PENDING` | Client sees network error | Reservation may or may not exist |
| Duplicate request while pending | `PENDING` | `409 order_in_progress` | No second reservation |

### Timeout ambiguity

A timeout is not proof that the reservation failed. The Inventory Service may have committed before the response was lost. The Order Service marks the order `FAILED` for audit, but does not automatically release or reverse stock. This is a known exactly-once limitation of a synchronous two-service write without a compensation workflow.

### Pending recovery

There is no background reconciler in this version. A `PENDING` order can be inspected by an operator, and the idempotent reservation endpoint can be queried by reservation ID if needed. A production design would add an outbox/worker, reservation expiry, and a reconciliation job.

## API Boundary and Trust

- Browser → nginx: untrusted input, rate-limited and size-limited at the Order Service.
- nginx → Order Service: trusted internal proxy; forwards client IP and request ID context.
- Order Service → Inventory Service: trusted service-to-service HTTP inside the Compose network.
- Services → databases: role-scoped credentials supplied through environment variables.

The Inventory Service is never published. This is enforced by Compose (`expose` only) rather than by application authentication.

## Security Architecture

See [Security](security.md) for the full control list. Architectural choices relevant here:

- Separate database roles prevent accidental cross-service table access.
- No cross-service database reads.
- Backend containers run as non-root with read-only root filesystems.
- nginx runs as the unprivileged nginx image.
- Same-origin API through nginx avoids browser CORS exposure in the normal path.
- Request body size and per-client rate limits are enforced before route handling.
- Error responses use a stable shape without echoing untrusted input.
- Security headers are set by both the API and nginx.
- Images use pinned dependency versions and multi-stage builds to reduce build tooling in runtime layers.

## Observability

Both services expose:

- `/health` — liveness/metadata.
- `/ready` — database readiness.
- `/metrics` — Prometheus text format.

The Order Service metrics endpoint is available directly on loopback. Inventory metrics remain internal and can be read with `docker compose exec`.

Structured JSON logs include:

- Request ID, method, route template, status, duration.
- Order ID, item count, total, failure code.
- Reservation ID, units, item count.
- Downstream target, operation, outcome, and duration.

Prometheus counters are per-process and reset when a container restarts.

## Test Strategy

| Layer | What it proves |
| --- | --- |
| Inventory service tests | Product CRUD, validation, reservation success, idempotent replay, insufficient stock, unknown products, concurrent oversell prevention, duplicate reservation races |
| Order service tests | Validation, idempotency, downstream failure mapping, replay behavior, concurrent duplicate creation, catalog proxy, client protocol handling |
| Integration tests | Real Order → Inventory ASGI flow, concurrent oversell prevention, failed-order retention |
| Security tests | Body limit, rate limit, CORS, validation error sanitization, security headers |
| Frontend tests | Form validation, idempotency header, success navigation, retained failure display, order/inventory rendering |

Backend tests use the dedicated test PostgreSQL on `55433`; they never use the application databases.

## Deliberate Deferrals

Not implemented in this phase:

- Authentication and authorization.
- TLS termination.
- A background reconciliation worker or outbox.
- Reservation expiry and stock release.
- Multi-replica rate limiting.
- Centralized logs, tracing, or dashboards.
- Backups and disaster recovery.
- CI/CD, image signing, SBOM generation, and vulnerability gates.

These are candidates for the next DevSecOps phases rather than hidden production claims.
