# Operations Runbook

These commands are verified on macOS with Docker Compose v2. They are local-development operations, not production procedures.

## Start and verify

```bash
cp .env.example .env
make up
make ps
make smoke
```

Open:

- Storefront: http://localhost:8080/store
- Operations console: http://localhost:8080/
- Order API and metrics: http://localhost:8000/health, http://localhost:8000/metrics

Expected state: `frontend`, `order-service`, `inventory-service`, and `postgres` are healthy; the smoke test creates and replays one operations order and one storefront checkout.

## Logs and health

```bash
docker compose ps
docker compose logs --tail=100
docker compose logs -f order-service
curl -fsS http://localhost:8080/health
curl -fsS http://localhost:8000/ready
docker compose exec inventory-service python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8001/ready').read().decode())"
```

## Persistence check

Create or use an existing order, then restart without deleting volumes:

```bash
make down
docker compose up -d --wait
curl -fsS 'http://localhost:8080/api/v1/orders?page_size=1'
docker volume ls --filter name=forge-platform
```

`make down` stops the default services plus the `test` and `observability` profile containers. It keeps `forge-platform_postgres-data`, `forge-platform_postgres-test-data`, `forge-platform_prometheus-data`, and `forge-platform_grafana-data`. Use `make clean` only when you intend to delete the database volumes.

Verified on 2026-10-28: orders and products survived a full down/up cycle, and both Alembic revisions remained at head.

## Migrations

```bash
docker compose exec -T order-service alembic current
docker compose exec -T inventory-service alembic current
docker compose exec -T order-service alembic upgrade head
docker compose exec -T inventory-service alembic upgrade head
```

The container entrypoint also retries `alembic upgrade head` before starting each backend.

## Tests

```bash
make test
```

This starts `postgres-test` on `127.0.0.1:55433`, runs the backend suite, then runs Vitest. It does not touch the application databases.

## Prometheus and Grafana

```bash
make observability-up
```

- Prometheus: http://127.0.0.1:9090
- Grafana: http://127.0.0.1:3001
- Default local login: `admin` / `forge_grafana_local_dev`
- Provisioned dashboard: **Forge Commerce Overview**

Verify targets:

```bash
curl -fsS 'http://127.0.0.1:9090/api/v1/targets?state=active' \
  | jq -r '.data.activeTargets[] | [.labels.job,.health] | @tsv'
```

Expected: `order-service up` and `inventory-service up`.

Stop monitoring:

```bash
make observability-down
```

## Deploy and rollback

Build and deploy a tagged image set:

```bash
./scripts/deploy-local.sh v1
./scripts/deploy-local.sh v2
./scripts/rollback-local.sh
```

Each deploy:

1. Builds all three application images with the requested tag.
2. Recreates the application containers.
3. Waits for health.
4. Runs the smoke test.
5. Records the previous tag in `.deploy/`.

Rollback restores the previous tag, waits for health, runs smoke, and swaps the recorded tags. The `.deploy/` directory is gitignored.

## Clean shutdown and reset

```bash
make down       # stop app, test, and monitoring containers; keep volumes
make clean      # stop everything and delete database volumes
```

After `make clean`, start from a clean database with:

```bash
docker compose up --build -d --wait
make smoke
```

## CI

The GitHub Actions workflow runs on `main` pushes and pull requests. Check the latest result at:

https://github.com/Ashwin1808/Forge-Ecom/actions/workflows/ci.yml

## Troubleshooting

- Port `3000` may be used by another local tool; Grafana is intentionally published on `3001`.
- If `localhost:3001` reaches an unrelated local app, use `127.0.0.1:3001`. macOS can resolve `localhost` to IPv6 while Compose publishes Grafana on IPv4 loopback.
- If a container is unhealthy, inspect `docker compose logs --tail=100 <service>` and the `/ready` endpoint.
- If tests cannot connect, run `docker compose --profile test up -d --wait postgres-test`.
- If Grafana has no data, confirm both Prometheus targets are `up` and wait for at least two scrape intervals (30 seconds).
