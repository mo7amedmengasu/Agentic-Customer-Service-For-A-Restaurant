import pytest

@pytest.fixture
def setup_order_data(client):
    """Creates user, menu_item, and order for linking items."""
    u_res = client.post(
        "/api/v1/users/",
        json={"user_email": "oi_tester@example.com", "user_password": "pw"}
    )
    uid = u_res.json()["user_id"] if u_res.status_code == 200 else 1

    mi_res = client.post(
        "/api/v1/menu-items/",
        json={"item_name": "Pizza", "item_price": 10.99}
    )
    miid = mi_res.json()["item_id"]

    o_res = client.post(
        "/api/v1/orders/",
        json={
            "customer_id": uid,
            "order_type": "delivery",
            "order_status": "preparing",
            "order_date": "2026-04-07T14:00:00Z"
        }
    )
    oid = o_res.json()["order_id"]
    return oid, miid

def test_create_order_item(client, setup_order_data):
    oid, miid = setup_order_data

    response = client.post(
        "/api/v1/order-items/",
        json={
            "order_id": oid,
            "item_id": miid,
            "item_name": "Pizza",
            "item_price": 10.99,
            "item_quantity": 2
        }
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["order_id"] == oid
    assert data["item_quantity"] == 2

def test_read_order_items(client, setup_order_data):
    oid, miid = setup_order_data
    
    response = client.get("/api/v1/order-items/")
    assert response.status_code == 200

def test_update_order_item(client, setup_order_data):
    oid, miid = setup_order_data
    
    # Needs created item
    client.post(
        "/api/v1/order-items/",
        json={
            "order_id": oid,
            "item_id": miid,
            "item_name": "Pizza",
            "item_price": 10.99,
            "item_quantity": 1
        }
    )
    update_res = client.put(
        f"/api/v1/order-items/{oid}/{miid}",
        json={"item_quantity": 5}
    )
    assert update_res.status_code == 200
    assert update_res.json()["item_quantity"] == 5
