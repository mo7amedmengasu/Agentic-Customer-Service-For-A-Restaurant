import pytest

@pytest.fixture
def setup_order(client):
    u_res = client.post(
        "/api/v1/users/",
        json={"user_email": "delivery_tester@example.com", "user_password": "pw"}
    )
    uid = u_res.json()["user_id"] if u_res.status_code == 200 else 1

    o_res = client.post(
        "/api/v1/orders/",
        json={
            "customer_id": uid,
            "order_type": "delivery",
            "order_status": "dispatched",
            "order_date": "2026-04-07T15:00:00Z"
        }
    )
    return o_res.json()["order_id"]

def test_create_delivery(client, setup_order):
    response = client.post(
        "/api/v1/deliveries/",
        json={
            "order_id": setup_order,
            "delivery_service": "DoorDash",
            "delivery_status": "en_route",
            "delivery_date": "2026-04-07T15:30:00Z"
        }
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["order_id"] == setup_order
    assert data["delivery_service"] == "DoorDash"
    assert "delivery_id" in data

def test_read_deliveries(client, setup_order):
    client.post(
        "/api/v1/deliveries/",
        json={
            "order_id": setup_order,
            "delivery_service": "UberEats",
            "delivery_status": "delivered",
            "delivery_date": "2026-04-07T16:00:00Z"
        }
    )
    
    response = client.get("/api/v1/deliveries/")
    assert response.status_code == 200
    assert len(response.json()) > 0
