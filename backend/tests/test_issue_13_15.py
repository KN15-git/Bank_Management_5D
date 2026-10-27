"""Standalone tests for Issues #13-#15 (history, filters/pagination, CSV export)."""
import pytest

from app import (
    AccountStatus,
    AccountType,
    Role,
    create_app,
    get_db,
    hash_password,
    init_db,
)


@pytest.fixture
def client(tmp_path):
    database_file = tmp_path / "transaction_history_test.db"
    app = create_app({
        "TESTING": True,
        "DATABASE_PATH": str(database_file),
        "SECRET_KEY": "test-key-for-transaction-history",
        "SESSION_COOKIE_SECURE": False,
    })
    with app.app_context():
        init_db()
        db = get_db()
        cursor = db.cursor()
        users = [
            ("admin1", "admin1@test.com", "Admin User", "AdminPass1", Role.ADMIN.value),
            ("emp1", "emp1@test.com", "Employee User", "EmpPass1", Role.EMPLOYEE.value),
            ("cust1", "cust1@test.com", "Customer One", "CustPass1", Role.CUSTOMER.value),
            ("cust2", "cust2@test.com", "Customer Two", "CustPass2", Role.CUSTOMER.value),
        ]
        user_ids = {}
        for username, email, full_name, password, role in users:
            cursor.execute(
                "INSERT INTO users (username, email, full_name, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
                (username, email, full_name, hash_password(password), role),
            )
            user_ids[username] = cursor.lastrowid

        accounts = [
            ("100000000001", user_ids["cust1"], AccountType.SAVINGS.value, 150000, AccountStatus.ACTIVE.value),
            ("100000000002", user_ids["cust1"], AccountType.CURRENT.value, 0, AccountStatus.ACTIVE.value),
            ("200000000001", user_ids["cust2"], AccountType.SAVINGS.value, 500000, AccountStatus.ACTIVE.value),
            ("100000000003", user_ids["cust1"], AccountType.SAVINGS.value, 100000, AccountStatus.FROZEN.value),
        ]
        cursor.executemany(
            "INSERT INTO accounts (account_number, user_id, account_type, balance, status) VALUES (?, ?, ?, ?, ?)",
            accounts,
        )
        db.commit()

    with app.test_client() as test_client:
        yield test_client


def login_customer(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "cust1", "password": "CustPass1"},
    )
    assert response.status_code == 200


def get_csrf(client):
    return client.get("/api/auth/csrf").get_json()["csrf_token"]


def deposit(client, amount, description):
    return client.post(
        "/api/accounts/1/deposit",
        headers={"X-CSRF-Token": get_csrf(client)},
        json={"amount": amount, "description": description},
    )


def test_history_has_pagination_metadata(client):
    login_customer(client)
    response = client.get("/api/accounts/1/transactions")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["transactions"] == []
    assert payload["pagination"] == {
        "page": 1,
        "per_page": 10,
        "total": 0,
        "total_pages": 0,
        "has_next": False,
        "has_previous": False,
    }


def test_type_filter_sort_and_pagination(client):
    login_customer(client)
    for amount in ("10.00", "20.00", "30.00"):
        assert deposit(client, amount, "test deposit").status_code == 201

    response = client.get(
        "/api/accounts/1/transactions?type=deposit&page=1&per_page=2&sort_by=amount&sort_order=asc"
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert [item["amount"] for item in payload["transactions"]] == ["10.00", "20.00"]
    assert payload["pagination"]["total"] == 3
    assert payload["pagination"]["total_pages"] == 2
    assert payload["pagination"]["has_next"] is True


def test_search_filter(client):
    login_customer(client)
    assert deposit(client, "25.00", "library test payment").status_code == 201
    response = client.get("/api/accounts/1/transactions?search=library%20test")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["pagination"]["total"] == 1
    assert payload["transactions"][0]["description"] == "library test payment"


def test_inclusive_date_filter(client):
    login_customer(client)
    assert deposit(client, "25.00", "date test").status_code == 201
    response = client.get("/api/accounts/1/transactions?date_from=2000-01-01&date_to=2099-12-31")
    assert response.status_code == 200
    assert response.get_json()["pagination"]["total"] == 1


def test_bad_filters_are_rejected(client):
    login_customer(client)
    assert client.get("/api/accounts/1/transactions?type=not-real").status_code == 400
    assert client.get("/api/accounts/1/transactions?sort_by=secret_column").status_code == 400
    assert client.get("/api/accounts/1/transactions?page=0").status_code == 400
    assert client.get("/api/accounts/1/transactions?date_from=bad-date").status_code == 400
    assert client.get("/api/accounts/1/transactions?date_from=2026-12-31&date_to=2026-01-01").status_code == 400


def test_other_customers_history_is_forbidden(client):
    login_customer(client)
    assert client.get("/api/accounts/3/transactions").status_code == 403
    assert client.get("/api/accounts/3/transactions/export").status_code == 403


def test_csv_export_respects_filters_and_attachment_headers(client):
    login_customer(client)
    assert deposit(client, "60.50", "statement test").status_code == 201
    assert deposit(client, "90.00", "other entry").status_code == 201

    response = client.get("/api/accounts/1/transactions/export?type=deposit&search=statement")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "attachment;" in response.headers.get("Content-Disposition", "")
    body = response.get_data(as_text=True)
    assert "Transaction Reference" in body
    assert "statement test" in body
    assert "60.50" in body
    assert "other entry" not in body


def test_csv_export_escapes_spreadsheet_formula_injection(client):
    login_customer(client)
    response = deposit(client, "10.00", "=HYPERLINK(\"https://example.invalid\")")
    assert response.status_code == 201
    export = client.get("/api/accounts/1/transactions/export")
    assert export.status_code == 200
    assert "'=HYPERLINK" in export.get_data(as_text=True)


def test_csv_export_includes_rows_after_first_hundred(client):
    login_customer(client)
    with client.application.app_context():
        db = get_db()
        db.executemany(
            """INSERT INTO transactions
               (reference_id, account_id, transaction_type, amount, balance_after, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (f"TXN-BULK-{index:03d}", 1, "deposit", 100, 150100, f"bulk row {index}", "2026-10-15 12:00:00")
                for index in range(105)
            ],
        )
        db.commit()

    response = client.get("/api/accounts/1/transactions/export")
    assert response.status_code == 200
    rows = response.get_data(as_text=True).splitlines()
    # One header plus 105 rows, even though the endpoint fetches in pages of 100.
    assert len(rows) == 106
    assert "bulk row 104" in response.get_data(as_text=True)
