"""Integration tests for profile and password settings (Issue #18)."""
import pytest
from app import create_app, init_db, get_db, hash_password, check_password


@pytest.fixture
def client(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE_PATH": str(tmp_path / "profile_test.db"),
        "SECRET_KEY": "profile-test-secret",
        "SESSION_COOKIE_SECURE": False,
    })
    with app.app_context():
        init_db()
        db = get_db()
        db.execute(
            "INSERT INTO users (username, email, full_name, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            ("profileuser", "profile@example.com", "Profile User", hash_password("OldPass123"), "customer"),
        )
        db.execute(
            "INSERT INTO users (username, email, full_name, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            ("otheruser", "other@example.com", "Other User", hash_password("OtherPass123"), "customer"),
        )
        db.commit()
    with app.test_client() as test_client:
        yield test_client


def login(client, username="profileuser", password="OldPass123"):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.get_json()["csrf_token"]


def test_profile_requires_authentication(client):
    response = client.patch("/api/auth/profile", json={"full_name": "New Name", "email": "new@example.com"})
    assert response.status_code == 401


def test_profile_update_refreshes_me_and_persists(client):
    csrf = login(client)
    response = client.patch(
        "/api/auth/profile",
        headers={"X-CSRF-Token": csrf},
        json={"full_name": "Updated Profile", "email": "UPDATED@example.com"},
    )
    assert response.status_code == 200
    assert response.get_json()["user"]["full_name"] == "Updated Profile"
    assert response.get_json()["user"]["email"] == "updated@example.com"

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["user"]["full_name"] == "Updated Profile"
    assert me.get_json()["user"]["email"] == "updated@example.com"


def test_profile_rejects_duplicate_email(client):
    csrf = login(client)
    response = client.patch(
        "/api/auth/profile", headers={"X-CSRF-Token": csrf},
        json={"full_name": "Profile User", "email": "other@example.com"},
    )
    assert response.status_code == 409


def test_profile_validation_and_csrf(client):
    csrf = login(client)
    bad_email = client.patch(
        "/api/auth/profile", headers={"X-CSRF-Token": csrf},
        json={"full_name": "Name", "email": "not-an-email"},
    )
    assert bad_email.status_code == 400
    missing_csrf = client.patch(
        "/api/auth/profile", json={"full_name": "Name", "email": "name@example.com"},
    )
    assert missing_csrf.status_code == 403


def test_password_change_checks_current_password_and_policy(client):
    csrf = login(client)
    wrong_current = client.patch(
        "/api/auth/password", headers={"X-CSRF-Token": csrf},
        json={"current_password": "WrongPass123", "new_password": "NewPass456"},
    )
    assert wrong_current.status_code == 400

    weak = client.patch(
        "/api/auth/password", headers={"X-CSRF-Token": csrf},
        json={"current_password": "OldPass123", "new_password": "weak"},
    )
    assert weak.status_code == 400

    success = client.patch(
        "/api/auth/password", headers={"X-CSRF-Token": csrf},
        json={"current_password": "OldPass123", "new_password": "NewPass456"},
    )
    assert success.status_code == 200
    relogin = client.post("/api/auth/login", json={"username": "profileuser", "password": "NewPass456"})
    assert relogin.status_code == 200


def test_user_cannot_change_another_users_profile(client):
    csrf = login(client)
    # The endpoint has no user-id path parameter and always targets current_user.
    response = client.patch(
        "/api/auth/profile", headers={"X-CSRF-Token": csrf},
        json={"user_id": 2, "full_name": "Attacker Update", "email": "attack@example.com"},
    )
    assert response.status_code == 200
    me = client.get("/api/auth/me").get_json()["user"]
    assert me["id"] == 1
    assert me["full_name"] == "Attacker Update"
    with client.application.app_context():
        db = get_db()
        other = db.execute("SELECT full_name, email FROM users WHERE id = 2").fetchone()
        assert other["full_name"] == "Other User"
        assert other["email"] == "other@example.com"
