# Interview Notes

These notes use only verified project evidence. Do not claim production scale, cloud deployment, authentication, payments, or a full CD platform.

## Resume bullets

- Built a two-service FastAPI and React commerce platform with PostgreSQL, Docker Compose, health checks, migrations, idempotent order/checkout flows, and inventory concurrency controls.
- Implemented GitHub Actions CI running 109 backend tests and 22 frontend tests, frontend lint/build, `pip-audit`, `npm audit`, Trivy secret/config scans, and HIGH/CRITICAL image scans for three images.
- Hardened application containers with non-root users, read-only backend filesystems, `no-new-privileges`, and an upgraded unprivileged nginx image; removed all HIGH/CRITICAL findings from the scanned application images.
- Added a loopback-only Prometheus/Grafana observability profile with service scrape configs, a 7-panel dashboard, and target-down/elevated-5xx alert rules.
- Built tagged local deploy and rollback scripts that rebuild images, wait for health, run smoke tests, and restore the previous tag.
- Verified database persistence across a full Compose down/up cycle and clean shutdown across application, test, and monitoring profiles.

## Avoid claiming

- Do not claim cloud deployment, Kubernetes, Terraform, Ansible, Jenkins, Argo CD, or GitOps.
- Do not claim authentication, authorization, payments, or Razorpay integration.
- Do not claim production HA, TLS, backups, Alertmanager, tracing, or SLOs.
- Do not claim SBOM, image signing, SAST, DAST, or a full git-history secret scan.
- Do not claim a percentage CVE reduction; say all HIGH/CRITICAL findings were removed from the scanned images.

## Scenario 1: CI backend job fails against PostgreSQL

**Situation:** The backend job passes locally but fails in GitHub Actions during database setup.

**Diagnosis:** Compare the service container port, health check, database URL, and whether the test databases exist. GitHub service containers are reachable on the job network, not `127.0.0.1`.

**Action:** Use a PostgreSQL 17 service on `55433`, wait for health, create `forge_orders_test` and `forge_inventory_test` with the bootstrap user, then run pytest with explicit test URLs.

**Result:** All 109 backend tests run in CI without relying on a developer machine.

**Follow-up:** Explain why test databases are separate from application databases and why trust authentication is limited to loopback.

## Scenario 2: Frontend image has HIGH/CRITICAL vulnerabilities

**Situation:** Trivy reports HIGH/CRITICAL findings in the nginx runtime image.

**Diagnosis:** Inspect the image OS packages and whether the image runs as root. Separate fixable OS findings from unfixed or application-dependency findings.

**Action:** Rebuild from the current unprivileged nginx base, run `apk upgrade --no-cache`, set `USER 101`, rebuild, and rescan. Keep the CI scan gate for future regressions.

**Result:** The frontend image scan reports 0 HIGH/CRITICAL findings; the container still serves the SPA and passes smoke.

**Follow-up:** Explain the tradeoff between rebuilding mutable tags and pinning digests for reproducibility.

## Scenario 3: `docker compose down` leaves containers and a network behind

**Situation:** After adding test and monitoring services, shutdown leaves profile containers running or the network cannot be removed.

**Diagnosis:** Compose profiles are opt-in. A plain `down` only removes active services, so profile containers can retain the project network.

**Action:** Make `make down` use `--profile test --profile observability down`, verify with `docker compose ps --all` and `docker network ls`, and keep named volumes.

**Result:** Shutdown removes all app, test, and monitoring containers plus the network while preserving database and monitoring volumes.

**Follow-up:** Explain the difference between `down`, `down -v`, and `stop`, and when each is appropriate.

## Scenario 4: Grafana dashboard shows no data

**Situation:** Grafana is healthy, but panels are empty.

**Diagnosis:** Check Prometheus targets, the datasource URL, scrape interval, the dashboard time range, and whether the app counters reset after a restart.

**Action:** Verify both targets are `UP`, query Prometheus directly, confirm the Grafana datasource health, generate traffic, and widen the time range. Use counters/rates that tolerate restarts.

**Result:** The dashboard shows live request rate and checkout/inventory metrics; target and error alerts are visible and inactive under normal load.

**Follow-up:** Explain why per-process counters reset, why `rate()` needs multiple samples, and what Alertmanager would add.

## Scenario 5: A bad deploy needs rollback

**Situation:** A new tagged image set fails health or smoke after deployment.

**Diagnosis:** Identify the current and previous tags, inspect container health and logs, and determine whether the failure is application, migration, or configuration related.

**Action:** Use `scripts/rollback-local.sh` to restore the previous tag, recreate the app containers, wait for health, and rerun smoke. Keep rollback state in `.deploy/` and out of Git.

**Result:** The previous tag is restored and verified; the failed tag remains available for debugging.

**Follow-up:** Explain why rollback must account for database migrations, why this local script is not a production deployment system, and what a real CD pipeline would add.
