def test_create_user(client):
    response = client.post(
        "/api/v1/users/",
        json={
            "user_email": "test@example.com",
            "user_password": "password123",
            "user_name": "Test User",
            "user_type": "customer",
            "user_tel": "1234567890"
        }
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["user_email"] == "test@example.com"
    assert data["user_name"] == "Test User"
    assert "user_id" in data

def test_read_users(client):
    client.post(
        "/api/v1/users/",
        json={
            "user_email": "list@example.com",
            "user_password": "password123",
            "user_name": "Listed User",
        }
    )
    response = client.get("/api/v1/users/")
    assert response.status_code == 200
    assert len(response.json()) > 0

def test_get_user_by_id(client):
    # Retrieve user 1 based on previous test execution (if tests run sequentially)
    # Better: create one and then get it to ensure isolation
    test_userResponse = client.post(
        "/api/v1/users/",
        json={"user_email": "test2@example.com", "user_password": "pass", "user_name": "Jane Doe"}
    )
    user_id = test_userResponse.json()["user_id"]
    
    response = client.get(f"/api/v1/users/{user_id}")
    assert response.status_code == 200
    assert response.json()["user_email"] == "test2@example.com"

def test_delete_user(client):
    test_userResponse = client.post(
        "/api/v1/users/",
        json={"user_email": "test_delete@example.com", "user_password": "pass"}
    )
    user_id = test_userResponse.json()["user_id"]
    
    # Delete User
    del_response = client.delete(f"/api/v1/users/{user_id}")
    assert del_response.status_code == 200

    # Ensure it's not found anymore
    get_response = client.get(f"/api/v1/users/{user_id}")
    assert get_response.status_code == 404


def test_login_returns_bearer_token(client):
    client.post(
        "/api/v1/users/",
        json={
            "user_email": "auth@example.com",
            "user_password": "password123",
            "user_name": "Auth User",
        },
    )

    response = client.post(
        "/api/v1/users/login",
        data={"username": "auth@example.com", "password": "password123"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]


def test_login_accepts_user_name(client):
    create_response = client.post(
        "/api/v1/users/",
        json={
            "user_email": "mohamed@example.com",
            "user_password": "1234",
            "user_name": "Mohamed",
        },
    )
    assert create_response.status_code == 200, create_response.text

    response = client.post(
        "/api/v1/users/login",
        data={"username": "Mohamed", "password": "1234"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]


def test_read_current_user_from_bearer_token(client):
    create_response = client.post(
        "/api/v1/users/",
        json={
            "user_email": "me@example.com",
            "user_password": "password123",
            "user_name": "Current User",
        },
    )
    assert create_response.status_code == 200, create_response.text

    login_response = client.post(
        "/api/v1/users/login",
        data={"username": "me@example.com", "password": "password123"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["user_email"] == "me@example.com"
    assert data["user_name"] == "Current User"
