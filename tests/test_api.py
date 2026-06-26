import os
import pytest
from fastapi.testclient import TestClient

# Add agent service to sys.path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services/agent"))

from main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_unauthenticated_scenarios():
    response = client.get("/scenarios")
    assert response.status_code == 401

def test_login_and_authenticated_request():
    response = client.post("/token", data={"username": "viewer", "password": "view123"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/scenarios", headers=headers)
    assert response.status_code == 200
    assert "scenarios" in response.json()
