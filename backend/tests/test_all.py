"""
Automated pytest suite for Bank Management System:
- Issue #2: Authentication & Login
- Issue #3: Role-Based Access Control
- Issue #4: Account & Balance Management
- Issue #5: Deposit Money
- Issue #6: Withdraw Money
- Issue #7: Transaction Validation & Recording
"""
import pytest
from app import create_app, init_db, get_db, Role, AccountStatus, AccountType, hash_password


@pytest.fixture
def client(tmp_path):
    db_file = tmp_path / "test_bank.db"
    test_config = {
        "TESTING": True,
        "DATABASE_PATH": str(db_file),
        "SECRET_KEY": "test-key-for-pytest-execution",
        "SESSION_COOKIE_SECURE": False,
    }
    app = create_app(test_config)

    with app.app_context():
        init_db()
        db = get_db()
        cursor = db.cursor()

        # Seed 1 admin, 1 employee, 2 customers
        cursor.execute(
            "INSERT INTO users (username, email, full_name, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            ("admin1", "admin1@test.com", "Admin User", hash_password("AdminPass1"), Role.ADMIN.value),
        )
        cursor.execute(
            "INSERT INTO users (username, email, full_name, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            ("emp1", "emp1@test.com", "Employee User", hash_password("EmpPass1"), Role.EMPLOYEE.value),
        )
        cursor.execute(
            "INSERT INTO users (username, email, full_name, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            ("cust1", "cust1@test.com", "Customer One", hash_password("CustPass1"), Role.CUSTOMER.value),
        )
        cust1_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO users (username, email, full_name, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            ("cust2", "cust2@test.com", "Customer Two", hash_password("CustPass2"), Role.CUSTOMER.value),
        )
        cust2_id = cursor.lastrowid

        # Seed accounts
        cursor.execute(
            "INSERT INTO accounts (account_number, user_id, account_type, balance, status) VALUES (?, ?, ?, ?, ?)",
            ("100000000001", cust1_id, AccountType.SAVINGS.value, 150000, AccountStatus.ACTIVE.value),  # ₹1500.00 (id 1)
        )
        cursor.execute(
            "INSERT INTO accounts (account_number, user_id, account_type, balance, status) VALUES (?, ?, ?, ?, ?)",
            ("100000000002", cust1_id, AccountType.CURRENT.value, 0, AccountStatus.ACTIVE.value),       # ₹0.00 (id 2)
        )
        cursor.execute(
            "INSERT INTO accounts (account_number, user_id, account_type, balance, status) VALUES (?, ?, ?, ?, ?)",
            ("200000000001", cust2_id, AccountType.SAVINGS.value, 500000, AccountStatus.ACTIVE.value),  # ₹5000.00 (id 3)
        )
        cursor.execute(
            "INSERT INTO accounts (account_number, user_id, account_type, balance, status) VALUES (?, ?, ?, ?, ?)",
            ("100000000003", cust1_id, AccountType.SAVINGS.value, 100000, AccountStatus.FROZEN.value),  # ₹1000.00 (id 4, Frozen)
        )
        db.commit()

    with app.test_client() as client:
        yield client


# ==============================================================================
# ISSUE #2: AUTHENTICATION TESTS
# ==============================================================================
def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "healthy"


def test_customer_registration_success(client):
    res = client.post(
        "/api/auth/register",
        json={
            "username": "new_cust",
            "email": "new_cust@example.com",
            "full_name": "New Customer",
            "password": "ValidPassword123",
        },
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["user"]["role"] == "customer"
    assert data["user"]["username"] == "new_cust"


def test_customer_registration_duplicate_username_email(client):
    res = client.post(
        "/api/auth/register",
        json={
            "username": "cust1",
            "email": "cust1@different.com",
            "full_name": "Duplicate User",
            "password": "ValidPassword123",
        },
    )
    assert res.status_code == 409
    assert "already registered" in res.get_json()["error"]


def test_customer_registration_weak_password(client):
    res = client.post(
        "/api/auth/register",
        json={
            "username": "weak_pw_user",
            "email": "weak@example.com",
            "full_name": "Weak PW",
            "password": "weak",
        },
    )
    assert res.status_code == 400
    assert "at least 8 characters" in res.get_json()["error"]


def test_login_success_and_session_persistence(client):
    login_res = client.post(
        "/api/auth/login",
        json={"username": "cust1", "password": "CustPass1"},
    )
    assert login_res.status_code == 200
    login_data = login_res.get_json()
    assert login_data["user"]["username"] == "cust1"
    assert "csrf_token" in login_data

    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert me_res.get_json()["user"]["username"] == "cust1"


def test_login_invalid_password(client):
    res = client.post(
        "/api/auth/login",
        json={"username": "cust1", "password": "WrongPassword123"},
    )
    assert res.status_code == 401
    assert res.get_json()["error"] == "Invalid credentials"


def test_login_brute_force_lockout(client):
    for i in range(5):
        res = client.post(
            "/api/auth/login",
            json={"username": "cust1", "password": "BadPassword123"},
        )
        if i < 4:
            assert res.status_code == 401
        else:
            assert res.status_code == 403
            assert "temporarily locked" in res.get_json()["error"]


def test_logout(client):
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
    logout_res = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logout_res.status_code == 200

    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 401


def test_csrf_protection_on_mutating_endpoints(client):
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    res_no_csrf = client.post("/api/accounts", json={"account_type": "savings"})
    assert res_no_csrf.status_code == 403
    assert "CSRF" in res_no_csrf.get_json()["error"]


# ==============================================================================
# ISSUE #3: RBAC & ADMIN TESTS
# ==============================================================================
def test_rbac_admin_endpoint_forbidden_for_customer(client):
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    res = client.get("/api/users")
    assert res.status_code == 403
    assert "insufficient permissions" in res.get_json()["error"]


def test_rbac_admin_can_list_users(client):
    client.post("/api/auth/login", json={"username": "admin1", "password": "AdminPass1"})
    res = client.get("/api/users")
    assert res.status_code == 200
    users = res.get_json()["users"]
    assert len(users) >= 4


def test_rbac_admin_cannot_demote_self(client):
    client.post("/api/auth/login", json={"username": "admin1", "password": "AdminPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
    res = client.patch(
        "/api/users/1/role",
        headers={"X-CSRF-Token": csrf},
        json={"role": "customer"},
    )
    assert res.status_code == 400
    assert "cannot change or demote their own role" in res.get_json()["error"]


def test_rbac_admin_cannot_deactivate_self(client):
    client.post("/api/auth/login", json={"username": "admin1", "password": "AdminPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
    res = client.patch(
        "/api/users/1/status",
        headers={"X-CSRF-Token": csrf},
        json={"is_active": False},
    )
    assert res.status_code == 400
    assert "cannot deactivate their own account" in res.get_json()["error"]


def test_rbac_ownership_isolation_between_customers(client):
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    res_own = client.get("/api/accounts/1")
    assert res_own.status_code == 200
    assert res_own.get_json()["account"]["account_number"] == "100000000001"

    res_other = client.get("/api/accounts/3")
    assert res_other.status_code == 403
    assert "do not own this account" in res_other.get_json()["error"]


def test_rbac_employee_can_access_any_customer_account(client):
    client.post("/api/auth/login", json={"username": "emp1", "password": "EmpPass1"})
    res1 = client.get("/api/accounts/1")
    assert res1.status_code == 200
    res2 = client.get("/api/accounts/3")
    assert res2.status_code == 200


# ==============================================================================
# ISSUE #4: ACCOUNT & BALANCE TESTS
# ==============================================================================
def test_customer_can_open_savings_account_for_self(client):
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
    res = client.post(
        "/api/accounts",
        headers={"X-CSRF-Token": csrf},
        json={"account_type": "savings", "initial_deposit": "250.75"},
    )
    assert res.status_code == 201
    acc = res.get_json()["account"]
    assert acc["balance"] == "250.75"
    assert acc["balance_paise"] == 25075
    assert len(acc["account_number"]) == 12


def test_employee_account_creation_for_customer(client):
    client.post("/api/auth/login", json={"username": "emp1", "password": "EmpPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
    res = client.post(
        "/api/accounts",
        headers={"X-CSRF-Token": csrf},
        json={"user_id": 4, "account_type": "current", "initial_deposit": "10000.00"},
    )
    assert res.status_code == 201
    acc = res.get_json()["account"]
    assert acc["balance"] == "10000.00"
    assert acc["account_type"] == "current"


def test_account_status_update_and_closure_rules(client):
    client.post("/api/auth/login", json={"username": "emp1", "password": "EmpPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]

    # Attempt to close non-zero account (id 1 has ₹1500.00) -> 400
    res_close_nonzero = client.patch(
        "/api/accounts/1/status",
        headers={"X-CSRF-Token": csrf},
        json={"status": "closed"},
    )
    assert res_close_nonzero.status_code == 400
    assert "Balance must be zero before closing" in res_close_nonzero.get_json()["error"]

    # Close zero balance account (id 2) -> 200
    res_close_zero = client.patch(
        "/api/accounts/2/status",
        headers={"X-CSRF-Token": csrf},
        json={"status": "closed"},
    )
    assert res_close_zero.status_code == 200
    assert res_close_zero.get_json()["account"]["status"] == "closed"


# ==============================================================================
# ISSUE #5: DEPOSIT MONEY TESTS
# ==============================================================================
def test_deposit_valid_amount_updates_balance(client):
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]

    # Initial balance is ₹1500.00; deposit ₹500.50 -> ₹2000.50
    res = client.post(
        "/api/accounts/1/deposit",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "500.50", "description": "ATM Cash Deposit"},
    )
    assert res.status_code == 201
    txn = res.get_json()["transaction"]
    assert txn["amount"] == "500.50"
    assert txn["amount_paise"] == 50050
    assert txn["balance_after"] == "2000.50"
    assert txn["transaction_type"] == "deposit"
    assert txn["reference_id"].startswith("TXN")

    # Verify balance endpoint reflects update
    bal_res = client.get("/api/accounts/1/balance")
    assert bal_res.get_json()["balance"] == "2000.50"


def test_deposit_invalid_negative_or_zero_amount(client):
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]

    # Zero amount
    res_zero = client.post(
        "/api/accounts/1/deposit",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "0.00"},
    )
    assert res_zero.status_code == 400
    assert "greater than zero" in res_zero.get_json()["error"]

    # Negative amount
    res_neg = client.post(
        "/api/accounts/1/deposit",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "-150.00"},
    )
    assert res_neg.status_code == 400
    assert "greater than zero" in res_neg.get_json()["error"]


def test_deposit_to_frozen_or_closed_account_rejected(client):
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]

    # Account 4 is frozen
    res_frozen = client.post(
        "/api/accounts/4/deposit",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "100.00"},
    )
    assert res_frozen.status_code == 403
    assert "frozen" in res_frozen.get_json()["error"]


# ==============================================================================
# ISSUE #6: WITHDRAW MONEY TESTS
# ==============================================================================
def test_withdraw_valid_amount_within_balance(client):
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]

    # Account 1 initial balance ₹1500.00; withdraw ₹500.00 -> balance becomes ₹1000.00
    res = client.post(
        "/api/accounts/1/withdraw",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "500.00", "description": "Branch cash withdrawal"},
    )
    assert res.status_code == 201
    txn = res.get_json()["transaction"]
    assert txn["amount"] == "500.00"
    assert txn["amount_paise"] == 50000
    assert txn["balance_after"] == "1000.00"
    assert txn["transaction_type"] == "withdrawal"

    bal_res = client.get("/api/accounts/1/balance")
    assert bal_res.get_json()["balance"] == "1000.00"


def test_withdraw_exceeding_balance_rejected(client):
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]

    # Balance is ₹1500.00; attempt to withdraw ₹2500.00
    res = client.post(
        "/api/accounts/1/withdraw",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "2500.00"},
    )
    assert res.status_code == 400
    assert "Insufficient funds" in res.get_json()["error"]

    # Ensure balance remained unchanged
    bal_res = client.get("/api/accounts/1/balance")
    assert bal_res.get_json()["balance"] == "1500.00"


def test_withdraw_from_other_customer_account_forbidden(client):
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]

    # cust1 attempts to withdraw from cust2's account (id 3)
    res = client.post(
        "/api/accounts/3/withdraw",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "50.00"},
    )
    assert res.status_code == 403
    assert "do not own this account" in res.get_json()["error"]


# ==============================================================================
# ISSUE #7: TRANSACTION RECORDING & AUDIT LOGS TESTS
# ==============================================================================
def test_transaction_ledger_records_and_retrieval(client):
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]

    # Deposit ₹300.00
    client.post(
        "/api/accounts/1/deposit",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "300.00", "description": "Salary Bonus"},
    )
    # Withdraw ₹100.00
    client.post(
        "/api/accounts/1/withdraw",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "100.00", "description": "Utility Bill"},
    )

    # Fetch transaction history
    res = client.get("/api/accounts/1/transactions")
    assert res.status_code == 200
    txns = res.get_json()["transactions"]
    assert len(txns) >= 2
    assert txns[0]["transaction_type"] == "withdrawal"
    assert txns[0]["amount"] == "100.00"
    assert txns[1]["transaction_type"] == "deposit"
    assert txns[1]["amount"] == "300.00"


def test_audit_log_entries_created(client):
    client.post("/api/auth/login", json={"username": "admin1", "password": "AdminPass1"})
    res = client.get("/api/health")
    assert res.status_code == 200
