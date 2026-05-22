import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_root(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_create_appointment(client):
    """Test creating appointment."""
    appointment_data = {
        "phone_number": "555-1234567",
        "doctor_name": "Dr. Smith",
        "appointment_date": "2024-06-15T10:00:00",
        "reason": "General checkup",
        "language": "en",
    }

    response = client.post("/api/appointments/", json=appointment_data)
    assert response.status_code == 200
    assert response.json()["phone_number"] == "555-1234567"


@pytest.mark.asyncio
async def test_list_appointments(client):
    """Test listing appointments."""
    response = client.get("/api/appointments/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
