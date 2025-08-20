import json
from flask_server import app


def test_health_endpoint_returns_healthy_status():
    with app.test_client() as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.content_type.startswith("application/json")
        data = resp.get_json()
        assert data == {"status": "healthy"}
