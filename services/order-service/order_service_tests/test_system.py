import pytest

pytestmark = pytest.mark.integration


def test_health_and_metrics(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["service"] == "order-service"

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "http_requests_total" in metrics.text
    assert "downstream_requests_total" in metrics.text


def test_readiness_reports_database(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok"}}


def test_readiness_failure_is_reported(app, client, monkeypatch):
    def fail():
        raise RuntimeError("database down")

    monkeypatch.setattr(app.state.db, "check", fail)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
