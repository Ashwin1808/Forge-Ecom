# Implementation Status

Last audited: 2026-10-28

This file records what is actually implemented and verified. A phase is only marked complete after its implementation and relevant tests have run successfully.

## Verification Snapshot

| Check | Result |
| --- | --- |
| Backend tests (`make test-backend`) | 75 passed |
| Frontend tests (`make test-frontend`) | 8 passed |
| Frontend build (`npm --prefix frontend run build`) | Passed |
| Frontend lint (`npm --prefix frontend run lint`) | Passed with 4 advisory `react(set-state-in-effect)` warnings |
| Docker Compose stack | frontend, order-service, inventory-service, postgres healthy |
| Smoke test | Order confirmed and idempotent replay verified |
| Git remote | `https://github.com/Ashwin1808/Forge-Ecom.git` |

## Baseline Capabilities

- React/TypeScript operations console with Overview, Orders, Order detail, New order, Inventory, and 404 screens.
- FastAPI Order Service exposing the public order and catalog APIs.
- FastAPI Inventory Service kept on the internal Docker network.
- PostgreSQL databases with separate owners for each service.
- Alembic migrations for both services.
- Atomic stock reservation with row locking, unique reservation IDs, and check constraints.
- Order creation idempotency with canonical request fingerprints.
- Failed orders retained for audit.
- Health, readiness, Prometheus metrics, structured logs, request IDs, rate limiting, body limits, security headers, and CORS restrictions.
- Multi-stage backend images, non-root users, read-only backend filesystems, and `no-new-privileges`.
- Idempotent development product seed.
- API, architecture, and security documentation.

## Phase Status

| Phase | Status | Notes |
| --- | --- | --- |
| 0. Repository audit | Complete | Architecture, features, gaps, and plan documented below. |
| 1. Customer storefront and operations separation | Not started | No customer storefront, cart, checkout, customer order history, or admin authorization. |
| 2. Razorpay test-mode payments | Not started | No payment model, Razorpay client, signature verification, webhook, or reconciliation. |
| 3. Database and API quality | Partial baseline | Migrations, constraints, validation, pagination, health, and error shape exist. Payment data, search/category, audit log, and new migrations are missing. |
| 4. Docker and local development | Partial baseline | Core stack exists. Prometheus, Grafana, OpenTelemetry, profiles, and resource settings are missing. |
| 5. CI/CD | Not started | No GitHub Actions or Jenkins pipelines. |
| 6. DevSecOps and supply chain | Partial baseline | Runtime hardening and input controls exist. Authentication, authorization, audit logging, SAST, dependency scanning, secret scanning, image scanning, and SBOM are missing. |
| 7. Terraform and cloud architecture | Not started | No Terraform modules or cloud deployment documentation. |
| 8. Ansible and Linux automation | Not started | No Ansible roles or playbooks. |
| 9. Kubernetes, Helm, and GitOps | Not started | No manifests, Helm chart, kind setup, or Argo CD configuration. |
| 10. Observability and SRE | Partial baseline | Metrics and JSON logs exist. Prometheus, Grafana, tracing, dashboards, alerts, SLIs/SLOs, and load tests are missing. |
| 11. Backup, restore, and incident response | Not started | No backup/restore scripts or incident runbooks. |
| 12. Interview and troubleshooting lab | Not started | No `docs/interview-lab/` scenarios. |
| 13. Documentation and project quality | Partial baseline | README, architecture, API, and security docs exist. Most requested documents and this status file are still pending. |

## Known Gaps and Risks

- No customer-facing storefront or customer identity.
- No authentication or authorization; all current screens are effectively administrative.
- No cart, checkout address, customer order lookup, or order history.
- No payment state, Razorpay integration, webhook verification, or payment reconciliation.
- Order status and payment status are not separated because payments do not exist yet.
- Reservations never expire or release stock; failed payments and abandoned checkouts cannot compensate inventory.
- Synchronous order creation has a documented timeout ambiguity and no outbox/reconciliation worker.
- No product search or category data model.
- Low-stock reporting exists only as client-side filtering in the dashboard.
- No administrative audit trail.
- No CI, dependency scanning, secret scanning, SAST, image scanning, or SBOM.
- No Prometheus/Grafana/OpenTelemetry services or dashboards.
- No Terraform, Ansible, Kubernetes, Helm, or GitOps assets.
- No backup/restore or incident runbooks.
- The frontend has 8 tests covering three operations pages; customer, cart, checkout, payment, and auth tests do not exist yet.
- Frontend lint reports four non-blocking `react(set-state-in-effect)` warnings.
- Base images are tag-pinned, not digest-pinned.
- Rate limiting is in-memory and per process.
- The Order Service is published directly on loopback in addition to nginx.

## External Requirements

- Razorpay test-mode credentials are required only for live test-checkout verification:
  - `RAZORPAY_KEY_ID`
  - `RAZORPAY_KEY_SECRET`
  - `RAZORPAY_WEBHOOK_SECRET`
- Mocked payment tests can be implemented and run without credentials.
- Optional tooling for later phases may need local installation: GitHub Actions runner access, Jenkins, Terraform, Ansible, kind, Helm, Argo CD, Trivy, Syft, Gitleaks, and Semgrep.

## Next Recommended Phase

Phase 1A: add a separate customer storefront and the backend/API support needed for catalog search, category filtering, cart, and checkout initiation, while preserving the existing operations console.

Before checkout is declared complete, define and implement:

- Customer vs operator access boundaries.
- Authoritative server-side pricing and stock validation.
- Payment state separate from order state.
- Stock reservation expiry/release.
- Idempotent checkout initiation.
- Tests for success, insufficient stock, invalid input, duplicate submissions, and downstream failures.
