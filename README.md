# Forge Commerce

[![CI](https://github.com/Ashwin1808/Forge-Ecom/actions/workflows/ci.yml/badge.svg)](https://github.com/Ashwin1808/Forge-Ecom/actions/workflows/ci.yml)

Forge Commerce is a local, production-shaped commerce workload built for DevSecOps exercises. It combines a React customer storefront and operations console, two FastAPI microservices, PostgreSQL, Docker Compose, automated tests, and explicit security boundaries.

The application is intentionally small enough to run on a laptop, but it exercises real failure modes: idempotent order creation and checkout, concurrent inventory reservation, reservation expiry and release, downstream timeouts, retained failed orders, health checks, migrations, and container hardening.

> This is a local development and training environment. It is not production-ready. See [Security](docs/security.md) for implemented controls and deliberate gaps.

## Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, React Router, Vitest + Testing Library |
| Order service | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL |
| Inventory service | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL |
| Edge | nginx unprivileged, serving the SPA and proxying the Order API |
| Containers | Docker Compose, multi-stage builds, non-root application users |
| Tests | pytest + httpx ASGI transport, Vitest + Testing Library |

## Architecture

```text
Browser (storefront + operations console)
  │
  ▼
nginx :8080  ── /api/* and /health ──▶  order-service :8000
  │ static SPA                                │
  │                                           ├──▶ PostgreSQL (forge_orders)
  │                                           │
  │                                           └──▶ inventory-service :8001
  │                                                     │
  │                                                     └──▶ PostgreSQL (forge_inventory)
  │
  └── only the frontend is published on the host
```

The Order Service also runs a checkout-expiry worker. It releases inventory holds through the internal Inventory Service and marks abandoned storefront checkouts `EXPIRED`.

- The frontend talks only to the Order Service through the nginx same-origin proxy.
- The Inventory Service is internal to the Compose network. It is not published to the host.
- Each service owns a separate database and role. The Order Service does not read inventory tables.
- The browser never receives inventory-service credentials or direct access.

The Order Service is also published on loopback at `http://localhost:8000` for API exploration and metrics. PostgreSQL and the Inventory Service are not published.

## Quick Start

Prerequisites:

- Docker Desktop or Docker Engine with Compose v2
- Ports `8080` and `8000` available on `127.0.0.1`
- About 2 GB of free disk space for images and volumes
- Python 3.12 and Node.js 24 only if you want to run tests or the frontend dev server

```bash
cp .env.example .env
docker compose up --build -d --wait
```

Open **http://localhost:8080/store** for the customer storefront or **http://localhost:8080/** for the operations console.

The first start automatically:

1. Creates the PostgreSQL roles and databases.
2. Runs Alembic migrations for both services.
3. Seeds six sample products in the Inventory Service.
4. Starts all health checks.

Verify the stack:

```bash
make ps
make smoke
```

`make smoke` exercises the real browser path through nginx: health, catalog, operations order creation, storefront checkout, and idempotent replay for both flows.

Useful commands:

```bash
make up              # Build and start the full stack
make logs            # Follow service logs
make down            # Stop app and test containers, keep volumes
make test            # Backend + frontend test suites
make seed            # Re-run the idempotent product seed
make clean           # Stop and delete database volumes
```

To stop the stack without deleting data:

```bash
make down
```

This also stops the `postgres-test` container. Raw `docker compose down` stops only the default services.

To reset all local data:

```bash
make clean
docker compose up --build -d --wait
```

## What You Can Do

### Customer storefront

- Browse the product catalog and product detail pages.
- Add products to a persistent browser cart, update quantities, and remove items.
- Enter customer and delivery details at checkout.
- Reserve an order with server-side price and stock validation.
- See the reservation hold, payment state, and delivery details on the confirmation page.
- Let abandoned reservations expire automatically, releasing inventory.

### Operations console

- View order counts, confirmation health, recent orders, and low-stock products.
- Browse the product catalog proxied from the Inventory Service.
- Create an order with one or more products.
- Watch the Order Service reserve stock synchronously through the Inventory Service.
- See confirmed orders with snapshotted names, SKUs, prices, and totals.
- See failed and expired orders retained for audit with a failure code and message.
- Replay an order safely with the same `Idempotency-Key`.
- Inspect Prometheus metrics, readiness, and structured logs.

## Order Lifecycle

### Operations orders

```text
POST /api/v1/orders
        │
        ▼
Create PENDING order + idempotency record
        │
        ▼
POST inventory reservation (reservation_id = order.id)
        │
        ├── success ──▶ CONFIRMED (snapshot items + total)
        │
        └── failure ──▶ FAILED (retained, failure_code/message)

Replay with the same Idempotency-Key
        ├── CONFIRMED ──▶ return the original order
        ├── FAILED ─────▶ return the original failure
        └── PENDING ────▶ 409 order_in_progress, Retry-After: 2
```

### Storefront checkout

```text
POST /api/v1/storefront/checkout
        │
        ▼
Create PENDING storefront order + customer/address snapshot + idempotency record
        │
        ▼
Reserve inventory (reservation_id = order.id)
        │
        ├── success ──▶ AWAITING_PAYMENT (payment_status = CREATED)
        │                  │
        │                  └── reservation expires ──▶ EXPIRED, stock released
        │
        └── failure ──▶ FAILED (retained, failure_code/message)

Replay with the same Idempotency-Key
        ├── AWAITING_PAYMENT / CONFIRMED ──▶ return the original order
        ├── EXPIRED ────────────────────────▶ 409 checkout_expired
        └── FAILED ─────────────────────────▶ return the original failure
```

Storefront checkout creates a real inventory reservation but does not collect payment. `payment_status=CREATED` records that a payment step would be next; no charge or payment object exists yet. The reservation TTL defaults to 15 minutes. A background worker releases expired reservations and marks the order `EXPIRED`.

Important failure semantics:

- **Insufficient stock:** the inventory transaction rolls back and the order is retained as `FAILED` with HTTP `409`.
- **Unknown product:** the order is retained as `FAILED` with HTTP `422`.
- **Inventory timeout/unavailable:** the order is retained as `FAILED` with HTTP `504`/`503`.
- **Timeout ambiguity:** if the Inventory Service commits a reservation but the Order Service times out waiting, the order is marked `FAILED` while stock may remain reserved. The expiry worker retries the release after the reservation TTL, so the window is bounded rather than permanent.
- **Crash after pending insert:** an order can remain `PENDING` until the expiry worker reconciles its reservation. Replays return `order_in_progress`; the console exposes the state rather than hiding it.
- **Failed and expired orders are never deleted** by the application; they remain visible for audit.

Inventory correctness:

- Reservations lock inventory rows with `SELECT ... FOR UPDATE` in product-ID order to prevent deadlocks and overselling.
- A unique reservation ID and request fingerprint make reservation calls idempotent.
- Database `CHECK` constraints prevent negative available or reserved quantities.
- Concurrent duplicate order creation is settled by a unique idempotency key at the database.

## API

Through the frontend proxy, use `http://localhost:8080`. Directly against the Order Service, use `http://localhost:8000`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness and service metadata |
| `GET` | `/ready` | Database readiness |
| `GET` | `/metrics` | Prometheus metrics (Order Service direct only) |
| `GET` | `/api/v1/products` | Paginated catalog proxy |
| `GET` | `/api/v1/products/{id}` | Product detail proxy |
| `POST` | `/api/v1/orders` | Create or replay an operations order |
| `GET` | `/api/v1/orders` | Paginated orders, optional `status` |
| `GET` | `/api/v1/orders/{id}` | Order detail |
| `GET` | `/api/v1/orders/{id}/items` | Order items |
| `POST` | `/api/v1/storefront/checkout` | Create or replay a storefront checkout |
| `GET` | `/api/v1/storefront/orders/{id}` | Storefront order confirmation |

Create an order:

```bash
curl -sS http://localhost:8080/api/v1/orders \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: demo-order-0001' \
  -d '{
    "customer": {"name": "Ada Lovelace", "email": "ada@example.com"},
    "items": [{"product_id": "<product-id>", "quantity": 1}]
  }'
```

The `Idempotency-Key` header is required. It must match `^[A-Za-z0-9._:-]{8,128}$`.

See [API reference](docs/api.md) for request/response shapes and error codes.

## Testing

Install the host development environment once:

```bash
make install-dev
```

Run everything:

```bash
make test
```

This starts the dedicated test PostgreSQL container on `127.0.0.1:55433`, then runs:

- **109 backend tests:** service unit/integration tests, cross-service storefront checkout and expiry tests, concurrency tests, and security hardening tests.
- **22 frontend tests:** storefront catalog/cart/checkout/order states, order creation and failure handling, validation, idempotency submission, order listing/filtering, and inventory rendering.

Individual suites:

```bash
make test-backend
make test-frontend
```

Test database details:

- Test containers use trust authentication and are bound to loopback only.
- The default URLs are `postgresql+psycopg://postgres@localhost:55433/forge_inventory_test` and `.../forge_orders_test`.
- Override with `TEST_INVENTORY_DATABASE_URL` and `TEST_ORDERS_DATABASE_URL`.
- Tests create and drop their own schemas; they do not touch the application databases.
- The test container is behind the Compose `test` profile and is not part of `docker compose up`.

The local host PostgreSQL that may already be using port `5432` is not required or modified. The test database uses port `55433`.

Backend test layout:

```text
services/inventory-service/inventory_service_tests/
services/order-service/order_service_tests/
tests/integration/
tests/security/
```

## Continuous Integration

The GitHub Actions workflow in `.github/workflows/ci.yml` runs on pushes to `main` and on pull requests:

- Backend tests against a PostgreSQL 17 service container.
- Frontend lint, Vitest, production build, and `npm audit`.
- Python dependency audit with `pip-audit`.
- Trivy secret and Docker/Compose misconfiguration scanning.
- Docker builds for the frontend, Order Service, and Inventory Service.
- Trivy high/critical image scans with unfixed vulnerabilities ignored.

The workflow uses only GitHub-hosted runners and the repository's existing dependencies. It does not deploy to a cloud account.

## Local Development

The supported workflow is containerized. To iterate on the frontend with hot reload while using the containerized API:

```bash
docker compose up -d postgres inventory-service order-service
npm --prefix frontend install
npm --prefix frontend run dev
```

Vite serves `http://localhost:5173` and proxies `/api` and `/health` to `http://localhost:8000`.

After backend changes:

```bash
docker compose up -d --build inventory-service order-service
```

Apply migrations manually:

```bash
docker compose exec order-service alembic upgrade head
docker compose exec inventory-service alembic upgrade head
```

Frontend checks:

```bash
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend test
```

## Configuration

Compose reads optional values from `.env`. Defaults are safe for local use only.

| Variable | Default | Purpose |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | `forge_postgres_local_dev` | PostgreSQL superuser password |
| `ORDER_DB_PASSWORD` | `forge_order_local_dev` | Password for the `forge_order` role |
| `INVENTORY_DB_PASSWORD` | `forge_inventory_local_dev` | Password for the `forge_inventory` role |
| `LOG_LEVEL` | `INFO` | Application log level |
| `ORDER_RATE_LIMIT_PER_MINUTE` | `120` | Per-client API request limit on the Order Service |
| `INVENTORY_RATE_LIMIT_PER_MINUTE` | `120` | Per-client API request limit on the Inventory Service |

Service-level settings can also be supplied as environment variables, including `DATABASE_URL`, `INVENTORY_BASE_URL`, `CORS_ORIGINS`, `SEED_ON_START`, `MAX_REQUEST_BYTES`, `CHECKOUT_RESERVATION_TTL_SECONDS`, `CHECKOUT_EXPIRY_ENABLED`, `CHECKOUT_EXPIRY_SWEEP_SECONDS`, and database pool/timeouts. Defaults live in each service's `config.py`.

Never commit `.env` or real credentials. The defaults exist only for the isolated local stack.

## Observability

- **Health:** `GET /health` reports service name, version, and environment.
- **Readiness:** `GET /ready` verifies database connectivity.
- **Metrics:** Prometheus text at `GET /metrics` on the Order Service (`http://localhost:8000/metrics`). The Inventory Service metrics endpoint is internal; inspect it with:

  ```bash
  docker compose exec inventory-service python -c \
    "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8001/metrics').read().decode())"
  ```

- **Logs:** structured JSON logs include request IDs, routes, status codes, durations, order IDs, and reservation outcomes. `X-Request-ID` is returned to clients and is included in error bodies.

Example metric names:

- `http_requests_total`
- `http_request_duration_seconds`
- `http_error_responses_total`
- `inventory_reservation_attempts_total`
- `inventory_units_reserved_total`
- `inventory_units_released_total`
- `order_creation_attempts_total`
- `checkout_attempts_total`
- `checkout_orders_expired_total`
- `downstream_requests_total`

## Repository Layout

```text
frontend/                     React storefront, operations console, and nginx config
services/order-service/       Public order API, workflow, client, migrations, tests
services/inventory-service/   Internal inventory API, transactions, migrations, tests
tests/integration/            Cross-service end-to-end tests
tests/security/               API hardening tests
database/init/                PostgreSQL roles and database bootstrap
docker/entrypoint.sh          Migration entrypoint for both backends
docs/                         Architecture, API, and security documentation
scripts/                      Seed and smoke-test helpers
docker-compose.yml            Local stack definition
Makefile                      Common developer commands
```

## Documentation

- [Architecture](docs/architecture.md): service boundaries, data model, workflows, consistency, and failure modes.
- [API reference](docs/api.md): endpoints, headers, payloads, status codes, and examples.
- [Security](docs/security.md): implemented controls, threat model, limitations, and next DevSecOps steps.

## Troubleshooting

**Ports already in use**

- `8080` or `8000` is occupied: stop the conflicting process or change the loopback port mapping in `docker-compose.yml`.
- Do not use host port `5432`; the stack keeps PostgreSQL internal. Test PostgreSQL uses `55433`.

**Stack is unhealthy**

```bash
docker compose ps
docker compose logs --tail=100
```

The backend entrypoint retries migrations for up to 30 seconds. If PostgreSQL was initialized with different credentials, reset the volume with `make clean`.

**No products in the console**

```bash
make seed
```

The seed is idempotent by SKU.

**Orders fail with inventory errors**

Check Inventory Service readiness and logs:

```bash
docker compose ps inventory-service
docker compose logs --tail=100 inventory-service
```

**Tests cannot connect**

```bash
docker compose --profile test up -d --wait postgres-test
docker compose ps postgres-test
```
