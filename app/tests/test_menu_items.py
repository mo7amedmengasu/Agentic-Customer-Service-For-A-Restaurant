def test_create_menu_item(client):
    response = client.post(
        "/api/v1/menu-items/",
        json={
            "item_name": "Cheeseburger",
            "item_description": "Delicious beef burger with cheese",
            "item_price": 9.99
        }
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["item_name"] == "Cheeseburger"
    assert data["item_price"] == "9.99" # Decimal is returned as string by Pydantic occasionally
    assert "item_id" in data

def test_read_menu_items(client):
    # Ensure there is at least one item
    client.post(
        "/api/v1/menu-items/",
        json={"item_name": "Fries", "item_price": 3.99}
    )
    
    response = client.get("/api/v1/menu-items/")
    assert response.status_code == 200
    assert len(response.json()) > 0
    assert any(item["item_name"] == "Fries" for item in response.json())

def test_update_menu_item(client):
    # Create item
    res = client.post(
        "/api/v1/menu-items/",
        json={"item_name": "Salad", "item_price": 5.99}
    )
    item_id = res.json()["item_id"]
    
    # Update item
    update_res = client.put(
        f"/api/v1/menu-items/{item_id}",
        json={"item_price": 6.99}
    )
    assert update_res.status_code == 200
    assert update_res.json()["item_price"] == "6.99"
