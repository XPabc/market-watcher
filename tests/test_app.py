import pytest
from fastapi.testclient import TestClient

from app import alerts, db
from app.main import app


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Every test gets its own empty database file."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()


@pytest.fixture
def client(fresh_db):
    # No "with" here on purpose: that would start the background poller,
    # and tests should never hit the real internet.
    return TestClient(app)


@pytest.mark.parametrize(
    "price, direction, threshold, expected",
    [
        (90, "below", 100, True),
        (110, "below", 100, False),
        (110, "above", 100, True),
        (90, "above", 100, False),
        (100, "above", 100, False),  # exactly equal is not a crossing
    ],
)
def test_is_crossed(price, direction, threshold, expected):
    assert alerts.is_crossed(price, direction, threshold) is expected


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_list_alert(client):
    response = client.post(
        "/alerts", json={"coin": "Bitcoin", "direction": "below", "price": 50000}
    )
    assert response.status_code == 201

    result = client.get("/alerts").json()
    assert len(result) == 1
    assert result[0]["id"] == response.json()["id"]
    assert result[0]["coin"] == "bitcoin"  # lower-cased
    assert result[0]["triggered"] is False


@pytest.mark.parametrize(
    "body",
    [
        {"coin": "bitcoin", "direction": "sideways", "price": 100},
        {"coin": "bitcoin", "direction": "below", "price": -5},
        {"coin": "", "direction": "below", "price": 100},
    ],
)
def test_rejects_invalid_alerts(client, body):
    assert client.post("/alerts", json=body).status_code == 422


def test_delete_alert(client):
    alert_id = client.post(
        "/alerts", json={"coin": "bitcoin", "direction": "above", "price": 1}
    ).json()["id"]
    assert client.delete(f"/alerts/{alert_id}").status_code == 204
    assert client.get("/alerts").json() == []


def test_delete_missing_alert_returns_404(client):
    assert client.delete("/alerts/999").status_code == 404


def test_prices_endpoint_returns_only_latest(client):
    db.save_prices({"bitcoin": 100.0})
    db.save_prices({"bitcoin": 110.0})
    result = client.get("/prices").json()
    assert len(result) == 1
    assert result[0]["price"] == 110.0


def test_alert_fires_once_then_rearms(fresh_db, monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "send_discord", lambda msg: sent.append(msg) or True)
    db.add_alert("bitcoin", "below", 100)

    alerts.check_alerts({"bitcoin": 90})   # crosses -> message
    alerts.check_alerts({"bitcoin": 80})   # still crossed -> no repeat
    assert len(sent) == 1

    alerts.check_alerts({"bitcoin": 120})  # back above -> re-armed
    alerts.check_alerts({"bitcoin": 95})   # crosses again -> second message
    assert len(sent) == 2


def test_failed_send_keeps_alert_armed(fresh_db, monkeypatch):
    monkeypatch.setattr(alerts, "send_discord", lambda msg: False)
    db.add_alert("bitcoin", "below", 100)
    alerts.check_alerts({"bitcoin": 90})
    assert db.list_alerts()[0]["triggered"] is False
