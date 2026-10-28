import pytest

pytestmark = pytest.mark.integration


def test_health_is_liveness_only(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "inventory-service"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_ready_checks_database(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok"}}


def test_metrics_exposes_prometheus_text(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "http_requests_total" in response.text
    assert "inventory_reservation_attempts_total" in response.text


def test_request_id_is_preserved_when_valid(client):
    response = client.get("/health", headers={"X-Request-ID": "test-request-1234"})
    assert response.headers["X-Request-ID"] == "test-request-1234"


def test_request_id_is_replaced_when_unsafe(client):
    response = client.get("/health", headers={"X-Request-ID": "<script>"})
    assert response.headers["X-Request-ID"] != "<script>"
    assert len(response.headers["X-Request-ID"]) >= 8
