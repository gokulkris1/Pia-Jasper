import pytest
from fastapi.testclient import TestClient
from mvp_ops_executor.app import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_chat_endpoint():
    response = client.post("/chat", json={"user": "test_user", "message": "Suspend SIM 8944123412341234567 immediately due to non payment"})
    assert response.status_code == 200
    assert "Confirm? yes/no" in response.json()["message"]