import pytest

@pytest.fixture
def setup_transaction_order(client):
    u_res = client.post(
        "/api/v1/users/",
        json={"user_email": "tx_tester@example.com", "user_password": "pw"}
    )
    uid = u_res.json()["user_id"] if u_res.status_code == 200 else 1

    o_res = client.post(
        "/api/v1/orders/",
        json={
            "customer_id": uid,
            "order_type": "dine_in",
            "order_status": "completed",
            "order_date": "2026-04-07T17:00:00Z"
        }
    )
    return o_res.json()["order_id"]

def test_create_transaction(client, setup_transaction_order):
    response = client.post(
        "/api/v1/transactions/",
        json={
            "order_id": setup_transaction_order,
            "tx_time": "2026-04-07T18:00:00Z",
            "tx_type": "credit_card",
            "tx_amount": 45.50,
            "tx_notes": "Paid in full"
        }
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["order_id"] == setup_transaction_order
    assert data["tx_type"] == "credit_card"
    assert data["tx_amount"] == "45.50" # Decimal comes as string
    assert "tx_id" in data

def test_read_transactions(client, setup_transaction_order):
    client.post(
        "/api/v1/transactions/",
        json={
            "order_id": setup_transaction_order,
            "tx_time": "2026-04-07T18:05:00Z",
            "tx_type": "cash",
            "tx_amount": 10.00
        }
    )
    
    response = client.get("/api/v1/transactions/")
    assert response.status_code == 200
    assert len(response.json()) > 0
