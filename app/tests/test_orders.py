import pytest

@pytest.fixture
def test_user(client):
    """Creates a user to attach orders to."""
    response = client.post(
        "/api/v1/users/",
        json={"user_email": "order_tester@example.com", "user_password": "password"}
    )
    # Check if duplicate email error (from sequential runs)
    if response.status_code == 400:
        return 1 # Fallback dummy ID if emails clash, though in-memory DB drops table session wide
    return response.json()["user_id"]

def test_create_order(client, test_user):
    response = client.post(
        "/api/v1/orders/",
        json={
            "customer_id": test_user,
            "order_type": "dine_in",
            "order_status": "pending",
            "order_date": "2026-04-07T12:00:00Z"
        }
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["customer_id"] == test_user
    assert data["order_status"] == "pending"
    assert "order_id" in data

def test_read_orders(client, test_user):
    client.post(
        "/api/v1/orders/",
        json={
            "customer_id": test_user,
            "order_type": "takeaway",
            "order_status": "completed",
            "order_date": "2026-04-07T13:00:00Z"
        }
    )
    
    response = client.get("/api/v1/orders/")
    assert response.status_code == 200
    assert len(response.json()) > 0
