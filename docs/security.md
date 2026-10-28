# Security

## Scope and Threat Model

Forge Commerce is a local development workload. It is suitable for practicing security automation, but it is not a public production system.

In-scope threats exercised by the current design:

- Malformed or oversized API requests.
- Injection attempts through validation boundaries.
- Idempotency-key abuse and duplicate order or checkout creation.
- Concurrent stock manipulation and overselling.
- Abandoned checkout reservations holding stock indefinitely.
- Cross-channel order data exposure between storefront and operations views.
- Error responses leaking untrusted input or internal details.
- Browser-side framing, MIME sniffing, and script injection through response headers.
- Accidental direct exposure of the internal Inventory Service or database.
- Container compromise through unnecessary privileges.

Out of scope for this version:

- Multi-tenant authentication and authorization.
- Internet-facing TLS and DDoS protection.
- Protection against a compromised Docker host.
- Supply-chain verification of base images and package artifacts.
- Regulatory data handling, PII retention, or audit-grade logging.

## Implemented Controls

### Input and API hardening

- Pydantic validation for all request bodies, query parameters, path IDs, and enums.
- Bounded strings, quantities, pagination, and item counts.
- Email validation and normalization.
- Rejection of duplicate product IDs within an order or reservation.
- Required `Idempotency-Key` with a constrained character set and length on order and checkout creation.
- Canonical request fingerprints for idempotency comparisons, including storefront customer/address data.
- Server-side price, stock, and total calculation; browser cart data is not trusted.
- Storefront order lookup is restricted to `channel=STOREFRONT`.
- Request body limit of 128 KiB by default for write methods.
- Per-client API rate limiting (120 requests/minute by default) with `Retry-After`.
- Validation error details are reduced to location, message, and type. Raw input values are not echoed.
- Unexpected exceptions and database errors return a generic `internal_error` body.
- Stable error shape with a request ID for correlation.
- Request IDs are validated before reuse; otherwise a new random ID is generated.

### Data integrity

- Separate PostgreSQL databases and roles for the two services.
- No cross-database foreign keys or direct table access between services.
- Database check constraints prevent negative inventory and invalid order states.
- Unique constraints enforce one idempotency record per key and one reservation line per product.
- Inventory rows are locked with `SELECT ... FOR UPDATE` in a deterministic order.
- Reservations, releases, and order creation use database transactions with rollback on failure.
- Stock shortage detection occurs before mutation.
- Release is idempotent and restores available stock exactly once.
- Checkout reservations carry an expiry; a background worker releases expired holds and marks orders `EXPIRED`.
- Database constraints enforce valid order status, payment status, channel, and reservation status.

### Browser and edge

- nginx serves static assets and proxies only `/api/*` and `/health`.
- nginx runs from the unprivileged nginx image on port `8080`.
- CSP restricts scripts, styles, images, connections, framing, and form targets.
- `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Cache-Control` headers are set.
- React escapes rendered data by default; no raw HTML rendering is used.
- CORS is disabled by default in the Inventory Service and restricted to local origins in the Order Service.
- The frontend does not use cookies or bearer tokens, so there is no cookie-based CSRF surface in the current design.

### Network exposure

- Only the frontend (`8080`) and Order Service (`8000`) are published, both bound to `127.0.0.1`.
- Inventory Service is exposed only on the Compose network.
- PostgreSQL is not published to the host.
- The test PostgreSQL is loopback-only and behind the `test` profile.
- Service-to-service calls use the Compose DNS name, not host networking.

### Containers

- Backend images use multi-stage builds; build tooling is not present in runtime images.
- Backends run as a dedicated non-root UID/GID `10001`.
- Backend root filesystems are read-only with a writable `/tmp` tmpfs.
- `no-new-privileges` is set on application containers.
- Application containers do not mount the Docker socket or host filesystems.
- Health checks verify readiness rather than only process liveness.
- Database migrations run from the container entrypoint before the app starts.

### Secrets and configuration

- No credentials are committed to the repository.
- `.env` is ignored; `.env.example` contains local-only defaults.
- Database credentials are injected through environment variables.
- The application does not log passwords, full connection URLs, or request bodies.
- Local defaults are explicitly labeled as local-only.

### Dependencies

- Python dependencies are pinned in compiled `requirements.txt` files.
- Frontend dependencies are locked in `package-lock.json`.
- Runtime images install from prebuilt wheels in a separate build stage.
- No cloud accounts, third-party APIs, or external data stores are required.

## Known Limitations

These are deliberate and should be addressed before treating the workload as production:

1. **No authentication or authorization.** Every local user can view and create orders. Storefront order lookup uses an unguessable UUID but has no customer identity check, so anyone with the URL can view that order.
2. **No TLS.** Traffic is HTTP on loopback. nginx does not terminate TLS.
3. **Rate limiting is per process and in memory.** Multiple replicas do not share counters.
4. **Proxy header trust.** The Order Service accepts forwarded client IP headers; it is only safe because the port is loopback-bound and nginx is the intended client. Public exposure would require a trusted-proxy allowlist.
5. **Secrets are plain environment variables.** Docker secrets or a secret manager are not used.
6. **Default credentials exist for local convenience.** They must never be reused outside this isolated stack.
7. **Base images are tag-pinned, not digest-pinned.** Tags can move.
8. **No image signing, SBOM, or vulnerability scanning in this phase.**
9. **No CI/CD pipeline or policy gates yet.** Tests are run manually or through Make.
10. **No WAF, bot protection, or DDoS mitigation.**
11. **No backup, restore, or retention policy.** `make clean` deletes volumes.
12. **No centralized logging or tracing.** Logs are local JSON on stdout.
13. **No payment processing or reconciliation.** Storefront orders stop at `AWAITING_PAYMENT`; `payment_status=CREATED` is not a paid state.
14. **Expiry is time-based, not exactly-once.** The worker retries failed releases, but a downstream outage can extend how long stock remains reserved.
15. **No audit trail for operator or customer actions.** There is no identity in this version.
16. **Test database uses trust authentication.** It is loopback-only, but it is not suitable for shared environments.

## Secure Local Operation

- Do not change the published ports to `0.0.0.0` without adding TLS, authentication, and network controls.
- Do not commit a real `.env`.
- Run `make clean` when disposing of local data.
- Keep Docker Desktop and images updated.
- Treat the default passwords as disposable and local-only.
- Use a dedicated machine or isolated environment for exercises.

## Recommended DevSecOps Next Steps

A pipeline for this workload should add, at minimum:

- **Secret scanning:** Gitleaks or TruffleHog on every commit.
- **Dependency scanning:** `pip-audit`, `npm audit`, Dependabot/Renovate.
- **SAST:** Semgrep or Bandit for Python, ESLint security rules for TypeScript.
- **Container scanning:** Trivy or Grype against built images.
- **SBOM:** Syft-generated SPDX or CycloneDX artifacts.
- **Signing and provenance:** Cosign signatures and SLSA-style provenance.
- **IaC scanning:** Checkov or Trivy config for Compose and Dockerfiles.
- **DAST:** OWASP ZAP baseline against the running frontend.
- **Policy gates:** Fail builds on critical vulnerabilities, unsigned images, or exposed secrets.
- **Runtime hardening:** read-only filesystems (already enabled for backends), dropped capabilities, seccomp/AppArmor profiles, and network policies.
- **Identity:** OIDC authentication for the console, customer order access control, and service-to-service credentials for the Inventory Service.
- **TLS:** terminate HTTPS at nginx or a local reverse proxy with trusted certificates.
- **Resilience:** outbox/reconciliation for operations orders, payment webhooks, and alerting on repeated expiry-release failures.
