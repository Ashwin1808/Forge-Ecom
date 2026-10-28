# Implementation Status

Last audited: 2026-10-28

This file records what is actually implemented and verified. A phase is only marked complete after its implementation and relevant tests have run successfully.

## Verification Snapshot

| Check | Result |
| --- | --- |
| Backend tests (`make test-backend`) | 109 passed |
| Frontend tests (`make test-frontend`) | 22 passed |
| Frontend build (`npm --prefix frontend run build`) | Passed |
| Frontend lint (`npm --prefix frontend run lint`) | Passed with no warnings |
| Docker Compose stack | frontend, order-service, inventory-service, postgres healthy after rebuild |
| Docker persistence | Orders and products survived a full `make down` / `up` cycle; database volumes were retained |
| Compose shutdown | `make down` removed app, test, and observability containers and the Compose network without orphaned resources |
| Migrations | Inventory `8d3f0b6a2c1e` and Order `4e8a1c2d7f90` applied on stack start; upgrade/downgrade/check verified on temporary databases |
| Smoke test (`make smoke`) | Operations order confirmed and replayed; storefront checkout returned `AWAITING_PAYMENT`/`CREATED` and replayed |
| Docker expiry worker | With a 5-second test TTL, a storefront checkout reached `EXPIRED` and stock returned to its pre-checkout available/reserved counts |
| CI | GitHub Actions run `40730320230` passed all backend, frontend, security, and container jobs on commit `e870c0e` |
| Security scans | `npm audit` 0; `pip-audit` no known vulnerabilities; Trivy image HIGH/CRITICAL 0; Trivy config 0; Trivy secrets 0 |
| Observability | Prometheus targets `UP`; Grafana healthy; datasource healthy; 7-panel dashboard provisioned; alerts inactive |
| Deploy and rollback | Tagged deploys `test-a`/`test-b` and rollback passed health and smoke checks |
| Git remote | `https://github.com/Ashwin1808/Forge-Ecom.git` |

## Implemented Capabilities

### Customer storefront

- Responsive storefront under `/store` with catalog, product detail, cart, checkout, confirmation, and not-found screens.
- Product listing and detail data loaded from the existing catalog proxy.
- Cart add/update/remove/clear with browser local-storage persistence.
- Checkout form for customer name/email and delivery address.
- Server-side price, stock, and total calculation; browser cart values are not trusted.
- Idempotent storefront checkout using `Idempotency-Key`.
- Orders created with `channel=STOREFRONT`, `status=AWAITING_PAYMENT`, and `payment_status=CREATED`.
- Storefront order confirmation shows reservation expiry, delivery details, and explicit “payment not connected” messaging.
- Storefront lookup is restricted to storefront-channel orders.

### Inventory reservation release and expiry

- Reservations support `RESERVED` and `RELEASED` states with `released_at`.
- Release restores available stock exactly once and is idempotent.
- Storefront checkout records `reservation_expires_at`.
- Order Service background worker releases expired reservations and marks orders `EXPIRED`.
- Failed release attempts remain retryable; failed timeout checkouts are cleaned up after expiry.
- Inventory metrics include units released; Order metrics include checkout outcomes and expired orders.

### Operations console

- React/TypeScript operations console with Overview, Orders, Order detail, New order, Inventory, and 404 screens.
- Dashboard, orders list, and order detail display the new order statuses, payment status, channel, delivery address, and reservation expiry.
- Existing operations order creation remains `CONFIRMED` and does not create a payment state.
- Operations-side link to the storefront is available without exposing operations screens to customers.

### Platform baseline

- FastAPI Order Service exposing public order, storefront, and catalog APIs.
- FastAPI Inventory Service kept on the internal Docker network.
- PostgreSQL databases with separate owners for each service.
- Alembic migrations for both services.
- Atomic stock reservation with row locking, unique reservation IDs, and check constraints.
- Order/checkout idempotency with canonical request fingerprints.
- Failed and expired orders retained for audit.
- Health, readiness, Prometheus metrics, structured logs, request IDs, rate limiting, body limits, security headers, and CORS restrictions.
- Multi-stage backend images, non-root users, read-only backend filesystems, and `no-new-privileges`.
- GitHub Actions CI with backend/frontend tests, dependency audits, Trivy scans, and image builds.
- Optional Prometheus/Grafana profile with a provisioned dashboard and starter alerts.
- Tagged local deploy and rollback scripts with health and smoke verification.
- Idempotent development product seed.
- API, architecture, operations, security, and portfolio documentation.

## Phase Status

| Phase | Status | Notes |
| --- | --- | --- |
| 0. Repository audit | Complete | Architecture, features, gaps, and plan documented below. |
| 1A. Customer storefront vertical slice | Complete | Storefront, cart, checkout, customer/address persistence, reservation expiry/release, and operations visibility implemented and tested. Search/category and customer identity were not part of this slice. |
| 1B. Customer/operator access separation | Not started | No authentication or authorization. Storefront order access is UUID-based only. |
| 2. Razorpay test-mode payments | Not started | No Razorpay client, signature verification, webhook, payment object, or reconciliation. Storefront orders stop at `AWAITING_PAYMENT` with `payment_status=CREATED`. |
| 3. Database and API quality | Partial baseline | Migrations, constraints, validation, pagination, health, error shape, storefront fields, and release state exist. Payment data, search/category, audit log, and customer order history are missing. |
| 4. Docker and local development | Mostly complete for local portfolio | Core stack, test profile, observability profile, health checks, and tagged deploy/rollback exist. OpenTelemetry and resource limits are missing. |
| 5. CI/CD | Partial | GitHub Actions CI is implemented and passing. Automated deployment/CD is intentionally not implemented. |
| 6. DevSecOps and supply chain | Partial | Runtime hardening, input controls, dependency audits, Trivy secret/config scans, and image scans exist. Authentication, authorization, audit logging, SAST, SBOM, and signing are missing. |
| 7. Terraform and cloud architecture | Not started | No Terraform modules or cloud deployment documentation. |
| 8. Ansible and Linux automation | Not started | No Ansible roles or playbooks. |
| 9. Kubernetes, Helm, and GitOps | Not started | No manifests, Helm chart, kind setup, or Argo CD configuration. |
| 10. Observability and SRE | Partial | Metrics, JSON logs, Prometheus, Grafana, a provisioned dashboard, and two starter alerts exist. Alertmanager, tracing, SLIs/SLOs, and load tests are missing. |
| 11. Backup, restore, and incident response | Not started | No backup/restore scripts or incident runbooks. |
| 12. Interview and troubleshooting lab | Partial | `docs/interview-notes.md` contains five verified scenarios; no separate `docs/interview-lab/` directory. |
| 13. Documentation and project quality | Mostly complete for local portfolio | README, architecture, API, operations, security, screenshots, finish plan, interview notes, and this status file exist. |

## Known Gaps and Risks

- No authentication or authorization; all current screens are effectively open to any local user.
- Storefront order lookup has no customer identity check; anyone with the UUID can view that order.
- No customer order history or account area.
- No payment collection, Razorpay integration, webhook verification, or payment reconciliation.
- `payment_status=CREATED` is a placeholder state, not evidence of a charge.
- Operations orders still use the synchronous create-and-confirm flow; a general outbox/reconciler is not implemented.
- Expiry release is retried but not exactly-once across a downstream outage; stock can remain reserved longer than the TTL.
- No product search or category data model.
- Low-stock reporting exists only as client-side filtering in the dashboard.
- No administrative audit trail.
- CI is verification only; there is no automated deployment or CD environment.
- No SAST, SBOM, image signing, provenance, or git-history secret scan.
- Prometheus/Grafana are local and single-node; there is no Alertmanager, tracing, SLO, or load test.
- No Terraform, Ansible, Kubernetes, Helm, or GitOps assets.
- No backup/restore or incident runbooks.
- Trivy filesystem scan reports one accepted `react-router-dom` 7.18.5 advisory; `npm audit` reports 0 and no fixed 7.x release is available.
- Base images are tag-pinned, not digest-pinned.
- Rate limiting is in-memory and per process.
- The Order Service is published directly on loopback in addition to nginx.

## External Requirements

- Razorpay test-mode credentials are required only for Phase 2 live test-checkout verification:
  - `RAZORPAY_KEY_ID`
  - `RAZORPAY_KEY_SECRET`
  - `RAZORPAY_WEBHOOK_SECRET`
- Mocked payment tests can be implemented and run without credentials.
- No additional credentials or cloud accounts are required for the current CI, monitoring, deploy, or rollback verification.

## Next Recommended Phase

For the current portfolio finish, stop here. The verified story is the application, tests, CI, security scans, Compose lifecycle, observability, and rollback.

If continuing later, Phase 1B should add customer/operator access boundaries and customer order access control. Phase 2 can then add Razorpay test-mode payment collection on top of the existing `AWAITING_PAYMENT` lifecycle.

Before payment is declared complete, define and implement:

- Payment objects/state separate from order state.
- Razorpay order creation and client handoff.
- Signature verification and idempotent webhook processing.
- Paid/failed/refunded transitions and reconciliation.
- Tests for success, signature failure, duplicate webhooks, retries, and downstream failures.
