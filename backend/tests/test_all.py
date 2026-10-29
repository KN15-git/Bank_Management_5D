"""
Automated pytest suite for Bank Management System:
- Issue #2: Authentication & Login
- Issue #3: Role-Based Access Control
- Issue #4: Account & Balance Management
- Issue #5: Deposit Money
- Issue #6: Withdraw Money
- Issue #7: Transaction Validation & Recording
- Issue #8: Fund Transfer Between Accounts
- Issue #9: Atomic Transfer & Rollback
- Issue #19: Data Security and Role Access
- Issue #20: System Response Time
- Issue #21: System Availability and Reliability
"""
import pytest
from app import (
    create_app,
    init_db,
    get_db,
    close_db,
    get_user_by_id,
    execute_transfer,
    Role,
    AccountStatus,
    AccountType,
    hash_password,
)


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


# ==============================================================================
# ISSUE #8 & #9: FUND TRANSFER & ATOMIC ROLLBACK TESTS
# ==============================================================================
def test_transfer_between_own_accounts_success(client):
    """Issue #8: Customer transfers funds between their own active accounts."""
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]

    # Account 1 has ₹1500.00; Account 2 has ₹0.00. Transfer ₹450.25 from Account 1 to Account 2.
    res = client.post(
        "/api/accounts/1/transfer",
        headers={"X-CSRF-Token": csrf},
        json={
            "destination_account_number": "100000000002",
            "amount": "450.25",
            "description": "Savings to Current transfer",
        },
    )
    assert res.status_code == 201
    data = res.get_json()
    trf = data["transfer"]
    assert trf["amount"] == "450.25"
    assert trf["amount_paise"] == 45025
    assert trf["source_account_number"] == "100000000001"
    assert trf["destination_account_number"] == "100000000002"
    assert trf["source_balance_after"] == "1049.75"
    assert trf["destination_balance_after"] == "450.25"
    assert trf["reference_id"].startswith("TXN")

    # Verify both balances updated accurately
    bal1 = client.get("/api/accounts/1/balance").get_json()
    bal2 = client.get("/api/accounts/2/balance").get_json()
    assert bal1["balance"] == "1049.75"
    assert bal1["balance_paise"] == 104975
    assert bal2["balance"] == "450.25"
    assert bal2["balance_paise"] == 45025

    # Verify ledger entries created on both accounts
    txns1 = client.get("/api/accounts/1/transactions").get_json()["transactions"]
    txns2 = client.get("/api/accounts/2/transactions").get_json()["transactions"]
    assert len(txns1) == 1
    assert txns1[0]["transaction_type"] == "transfer_out"
    assert txns1[0]["amount"] == "450.25"
    assert txns1[0]["balance_after"] == "1049.75"

    assert len(txns2) == 1
    assert txns2[0]["transaction_type"] == "transfer_in"
    assert txns2[0]["amount"] == "450.25"
    assert txns2[0]["balance_after"] == "450.25"


def test_transfer_to_another_customer_account_and_transfer_history(client):
    """Issue #8: Customer transfers funds to another customer's account and views transfer list."""
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]

    # Account 1 (cust1, ₹1500.00) -> Account 3 (cust2, 200000000001, ₹5000.00), amount ₹500.00
    res = client.post(
        "/api/transfers",
        headers={"X-CSRF-Token": csrf},
        json={
            "source_account_id": 1,
            "destination_account_number": "200000000001",
            "amount": "500.00",
            "description": "Rent payment to cust2",
        },
    )
    assert res.status_code == 201
    trf = res.get_json()["transfer"]
    assert trf["source_balance_after"] == "1000.00"
    assert trf["destination_balance_after"] == "5500.00"

    # Check transfer history on source account
    trf_list_res = client.get("/api/accounts/1/transfers")
    assert trf_list_res.status_code == 200
    transfers = trf_list_res.get_json()["transfers"]
    assert len(transfers) == 1
    assert transfers[0]["direction"] == "outgoing"
    assert transfers[0]["amount"] == "500.00"

    # Login as cust2 and verify their balance and incoming transfer record
    client.post("/api/auth/login", json={"username": "cust2", "password": "CustPass2"})
    bal3 = client.get("/api/accounts/3/balance").get_json()
    assert bal3["balance"] == "5500.00"

    trf_list_cust2 = client.get("/api/accounts/3/transfers").get_json()["transfers"]
    assert len(trf_list_cust2) == 1
    assert trf_list_cust2[0]["direction"] == "incoming"


def test_transfer_insufficient_funds_rejected_and_atomic(client):
    """Issue #8 & #9: Transfer exceeding balance is rejected and neither account changes."""
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]

    res = client.post(
        "/api/accounts/1/transfer",
        headers={"X-CSRF-Token": csrf},
        json={
            "destination_account_number": "200000000001",
            "amount": "2000.00",
        },
    )
    assert res.status_code == 400
    assert "Insufficient funds" in res.get_json()["error"]

    # Source account still ₹1500.00 and no transactions recorded
    assert client.get("/api/accounts/1/balance").get_json()["balance"] == "1500.00"
    assert len(client.get("/api/accounts/1/transactions").get_json()["transactions"]) == 0


def test_transfer_validation_errors(client):
    """Issue #8: Validate self-transfer, non-existent destination, zero/negative amounts, and unauthorized source."""
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]

    # 1. Self-transfer rejected
    res_same = client.post(
        "/api/accounts/1/transfer",
        headers={"X-CSRF-Token": csrf},
        json={"destination_account_number": "100000000001", "amount": "100.00"},
    )
    assert res_same.status_code == 400
    assert "same account" in res_same.get_json()["error"]

    # 2. Non-existent destination account -> 404
    res_missing = client.post(
        "/api/accounts/1/transfer",
        headers={"X-CSRF-Token": csrf},
        json={"destination_account_number": "999999999999", "amount": "100.00"},
    )
    assert res_missing.status_code == 404
    assert "Destination account not found" in res_missing.get_json()["error"]

    # 3. Zero or negative amount -> 400
    res_zero = client.post(
        "/api/accounts/1/transfer",
        headers={"X-CSRF-Token": csrf},
        json={"destination_account_number": "200000000001", "amount": "0.00"},
    )
    assert res_zero.status_code == 400
    assert "greater than zero" in res_zero.get_json()["error"]

    res_neg = client.post(
        "/api/accounts/1/transfer",
        headers={"X-CSRF-Token": csrf},
        json={"destination_account_number": "200000000001", "amount": "-50.00"},
    )
    assert res_neg.status_code == 400

    # 4. Unauthorized transfer from another customer's account -> 403
    res_unauth = client.post(
        "/api/accounts/3/transfer",
        headers={"X-CSRF-Token": csrf},
        json={"destination_account_number": "100000000001", "amount": "50.00"},
    )
    assert res_unauth.status_code == 403
    assert "do not own this account" in res_unauth.get_json()["error"]


def test_transfer_frozen_or_closed_accounts_rejected(client):
    """Issue #8: Transfers from or to frozen or closed accounts are blocked."""
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]

    # 1. Source account 4 is frozen -> 403
    res_src_frozen = client.post(
        "/api/accounts/4/transfer",
        headers={"X-CSRF-Token": csrf},
        json={"destination_account_number": "100000000001", "amount": "100.00"},
    )
    assert res_src_frozen.status_code == 403
    assert "frozen" in res_src_frozen.get_json()["error"]

    # 2. Destination account 4 is frozen -> 403
    res_dest_frozen = client.post(
        "/api/accounts/1/transfer",
        headers={"X-CSRF-Token": csrf},
        json={"destination_account_number": "100000000003", "amount": "100.00"},
    )
    assert res_dest_frozen.status_code == 403
    assert "frozen" in res_dest_frozen.get_json()["error"]

    # 3. Close zero-balance account 2 as employee, then attempt transfer to it -> 400
    client.post("/api/auth/login", json={"username": "emp1", "password": "EmpPass1"})
    emp_csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
    client.patch(
        "/api/accounts/2/status",
        headers={"X-CSRF-Token": emp_csrf},
        json={"status": "closed"},
    )

    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    cust_csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
    res_dest_closed = client.post(
        "/api/accounts/1/transfer",
        headers={"X-CSRF-Token": cust_csrf},
        json={"destination_account_number": "100000000002", "amount": "100.00"},
    )
    assert res_dest_closed.status_code == 400
    assert "closed" in res_dest_closed.get_json()["error"]


def test_atomic_transfer_rollback_on_mid_transaction_failure(client):
    """
    Issue #9: Verify all-or-nothing atomicity.
    If an error occurs after the source account is debited (or during ledger recording),
    the entire transaction rolls back so source balance is never debited without destination credit.
    """
    app = client.application
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cust1 = get_user_by_id(3)

        # Case A: Simulated failure right after debiting source account
        res, err, code = execute_transfer(
            user=cust1,
            source_account_id=1,
            destination_account_number="200000000001",
            amount_rupees="400.00",
            description="Should rollback",
            _simulate_failure_after_debit=True,
        )
        assert res is None
        assert code == 500
        assert "rolled back" in err

        # Verify source account 1 still has 150000 paise (₹1500.00) and destination account 3 still has 500000 paise (₹5000.00)
        cursor.execute("SELECT balance FROM accounts WHERE id = 1")
        assert cursor.fetchone()["balance"] == 150000
        cursor.execute("SELECT balance FROM accounts WHERE id = 3")
        assert cursor.fetchone()["balance"] == 500000

        # Verify no partial rows exist in transactions or transfers
        cursor.execute("SELECT COUNT(*) AS cnt FROM transactions")
        assert cursor.fetchone()["cnt"] == 0
        cursor.execute("SELECT COUNT(*) AS cnt FROM transfers")
        assert cursor.fetchone()["cnt"] == 0

        # Case B: Database trigger failure during credit / ledger insertion via HTTP endpoint
        cursor.execute(
            """
            CREATE TRIGGER fail_on_transfer_insert
            BEFORE INSERT ON transfers
            BEGIN
                SELECT RAISE(ABORT, 'Database ledger failure during transfer');
            END;
            """
        )
        db.commit()

    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
    http_res = client.post(
        "/api/accounts/1/transfer",
        headers={"X-CSRF-Token": csrf},
        json={"destination_account_number": "200000000001", "amount": "300.00"},
    )
    assert http_res.status_code == 500
    assert "rolled back" in http_res.get_json()["error"]

    # Both balances and transaction ledgers must remain completely unchanged
    assert client.get("/api/accounts/1/balance").get_json()["balance"] == "1500.00"
    assert len(client.get("/api/accounts/1/transactions").get_json()["transactions"]) == 0


# ==============================================================================
# ISSUE #19: DATA SECURITY & ROLE ACCESS TESTS
# ==============================================================================
def test_issue_19_security_headers_and_cache_control(client):
    res = client.get('/api/health')
    assert res.status_code == 200
    assert res.headers.get('X-Content-Type-Options') == 'nosniff'
    assert res.headers.get('X-Frame-Options') == 'DENY'
    assert 'no-store' in res.headers.get('Cache-Control', '')
    assert 'Strict-Transport-Security' in res.headers


def test_issue_19_no_plaintext_passwords_in_db_or_api(client):
    # Verify passwords stored as bcrypt hashes only, never plain text
    with client.application.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT password_hash FROM users')
        rows = cursor.fetchall()
        for r in rows:
            h = r['password_hash']
            assert h.startswith('$') or h.startswith('$')
            assert 'AdminPassword' not in h
            assert 'Bank@1234' not in h


# ==============================================================================
# ISSUE #20: SYSTEM RESPONSE TIME TESTS
# ==============================================================================
def test_issue_20_system_response_time_under_threshold(client):
    import time
    start = time.time()
    res = client.get('/api/health')
    elapsed = time.time() - start
    assert res.status_code == 200
    # Requirement: response time must complete well under 2-3 seconds threshold
    assert elapsed < 1.0
    assert 'X-Response-Time' in res.headers
    assert 'Server-Timing' in res.headers


# ==============================================================================
# ISSUE #21: SYSTEM AVAILABILITY AND RELIABILITY TESTS
# ==============================================================================
def test_issue_21_health_and_readiness_diagnostics(client):
    """Issue #21: Verify liveness and readiness probes report DB connectivity, schema integrity, and uptime."""
    for endpoint in ("/api/health", "/api/health/ready"):
        res = client.get(endpoint)
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "healthy"
        assert data["service"] == "Bank Management System API"
        assert data["db_connected"] is True
        assert data["integrity"] == "ok"
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0


def test_issue_21_graceful_degradation_and_recovery_on_db_failure(client, monkeypatch):
    """
    Issue #21: When the database encounters an operational failure, health checks and endpoints
    degrade gracefully with structured 503 JSON instead of crashing, and recover automatically.
    """
    import sqlite3
    import app as app_module

    def broken_get_db():
        raise sqlite3.OperationalError("simulated database connection failure")

    monkeypatch.setattr(app_module, "get_db", broken_get_db)

    res_degraded = client.get("/api/health")
    assert res_degraded.status_code == 503
    data_degraded = res_degraded.get_json()
    assert data_degraded["status"] == "unhealthy"
    assert data_degraded["db_connected"] is False
    assert "Database unavailable" in data_degraded["error"]

    # Restore database connection helper and verify immediate self-healing recovery
    monkeypatch.undo()
    res_recovered = client.get("/api/health")
    assert res_recovered.status_code == 200
    assert res_recovered.get_json()["status"] == "healthy"
    assert res_recovered.get_json()["db_connected"] is True


def test_issue_21_teardown_rollback_and_fault_isolation(client):
    """
    Issue #21: Verify uncommitted changes are automatically rolled back if an unhandled exception
    occurs during request teardown, preserving data consistency for subsequent requests.
    """
    app = client.application
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE accounts SET balance = 999999 WHERE id = 1")
        # Simulate an unhandled exception passed into close_db teardown
        close_db(RuntimeError("Simulated unhandled request error"))

    # Subsequent request should see the original committed balance (₹1500.00 / 150000 paise)
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    bal_res = client.get("/api/accounts/1/balance")
    assert bal_res.status_code == 200
    assert bal_res.get_json()["balance"] == "1500.00"
    assert bal_res.get_json()["balance_paise"] == 150000


def test_issue_21_sustained_load_availability_and_consistency(client):
    """
    Issue #21: Verify 100% system availability and financial consistency across a burst of
    valid and invalid operations (interleaving deposits, failed overdrafts, transfers, and health checks).
    """
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]

    # Execute 10 interleaved cycles of valid deposits, invalid overdraft attempts, and valid transfers
    for _ in range(10):
        dep_res = client.post(
            "/api/accounts/1/deposit",
            headers={"X-CSRF-Token": csrf},
            json={"amount": "100.00", "description": "Load test deposit"},
        )
        assert dep_res.status_code == 201

        # Invalid overdraft attempt in the middle of valid traffic must fail cleanly without corrupting state
        bad_wdr = client.post(
            "/api/accounts/1/withdraw",
            headers={"X-CSRF-Token": csrf},
            json={"amount": "999999.00"},
        )
        assert bad_wdr.status_code == 400

        trf_res = client.post(
            "/api/accounts/1/transfer",
            headers={"X-CSRF-Token": csrf},
            json={"destination_account_number": "100000000002", "amount": "40.00"},
        )
        assert trf_res.status_code == 201

        health_res = client.get("/api/health")
        assert health_res.status_code == 200

    # Initial: Acc 1 = ₹1500.00, Acc 2 = ₹0.00
    # After 10 cycles of (+100.00 - 40.00): Acc 1 = ₹2100.00, Acc 2 = ₹400.00
    assert client.get("/api/accounts/1/balance").get_json()["balance"] == "2100.00"
    assert client.get("/api/accounts/2/balance").get_json()["balance"] == "400.00"


# ==============================================================================
# ISSUE #10, #11, #12: LOAN APPLICATION, REVIEW & APPROVAL/REJECTION TESTS
# ==============================================================================
def test_issue_10_customer_submit_loan_application_success(client):
    """Issue #10: Authenticated customer submits a valid loan application and receives a reference ID and pending status."""
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]

    res = client.post(
        "/api/loans",
        headers={"X-CSRF-Token": csrf},
        json={
            "loan_type": "home",
            "amount": "250000.00",
            "term_months": 60,
            "account_id": 1,
            "purpose": "Purchase of residential apartment",
        },
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["message"] == "Loan application submitted successfully"
    loan = data["loan"]
    assert loan["reference_id"].startswith("LN")
    assert loan["loan_type"] == "home"
    assert loan["amount"] == "250000.00"
    assert loan["amount_paise"] == 25000000
    assert loan["term_months"] == 60
    assert loan["account_id"] == 1
    assert loan["purpose"] == "Purchase of residential apartment"
    assert loan["status"] == "pending"
    assert loan["reviewed_by"] is None


def test_issue_10_loan_application_validation_errors(client):
    """Issue #10: Missing or invalid loan fields (amount, type, term, purpose, unowned account) are rejected with 400/403."""
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]

    # Missing amount
    res_no_amt = client.post(
        "/api/loans",
        headers={"X-CSRF-Token": csrf},
        json={"loan_type": "personal", "term_months": 12, "purpose": "Medical expenses"},
    )
    assert res_no_amt.status_code == 400

    # Zero or negative amount
    res_bad_amt = client.post(
        "/api/loans",
        headers={"X-CSRF-Token": csrf},
        json={"loan_type": "personal", "amount": "-500.00", "term_months": 12, "purpose": "Medical"},
    )
    assert res_bad_amt.status_code == 400

    # Invalid loan type
    res_bad_type = client.post(
        "/api/loans",
        headers={"X-CSRF-Token": csrf},
        json={"loan_type": "crypto", "amount": "5000.00", "term_months": 12, "purpose": "Speculation"},
    )
    assert res_bad_type.status_code == 400

    # Invalid term_months
    res_bad_term = client.post(
        "/api/loans",
        headers={"X-CSRF-Token": csrf},
        json={"loan_type": "personal", "amount": "5000.00", "term_months": 0, "purpose": "Travel"},
    )
    assert res_bad_term.status_code == 400

    # Blank purpose
    res_no_purpose = client.post(
        "/api/loans",
        headers={"X-CSRF-Token": csrf},
        json={"loan_type": "personal", "amount": "5000.00", "term_months": 12, "purpose": "   "},
    )
    assert res_no_purpose.status_code == 400

    # Account owned by another customer (cust2 owns account 3)
    res_other_acc = client.post(
        "/api/loans",
        headers={"X-CSRF-Token": csrf},
        json={
            "loan_type": "personal",
            "amount": "5000.00",
            "term_months": 12,
            "account_id": 3,
            "purpose": "Personal use",
        },
    )
    assert res_other_acc.status_code == 403


def test_issue_11_loan_review_queue_and_ownership_isolation(client):
    """
    Issue #11: Customers only see their own loans; Employees and Admins see all loans in the review queue
    and can filter by status.
    """
    # cust1 submits a loan
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf1 = client.get("/api/auth/csrf").get_json()["csrf_token"]
    r1 = client.post(
        "/api/loans",
        headers={"X-CSRF-Token": csrf1},
        json={"loan_type": "education", "amount": "80000.00", "term_months": 36, "purpose": "University tuition"},
    )
    assert r1.status_code == 201
    loan1_id = r1.get_json()["loan"]["id"]
    client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf1})

    # cust2 submits a loan
    client.post("/api/auth/login", json={"username": "cust2", "password": "CustPass2"})
    csrf2 = client.get("/api/auth/csrf").get_json()["csrf_token"]
    r2 = client.post(
        "/api/loans",
        headers={"X-CSRF-Token": csrf2},
        json={"loan_type": "vehicle", "amount": "120000.00", "term_months": 48, "purpose": "Two-wheeler purchase"},
    )
    assert r2.status_code == 201
    loan2_id = r2.get_json()["loan"]["id"]

    # cust2 can only see own loan in list and is forbidden (403) from viewing cust1's loan
    cust2_loans = client.get("/api/loans").get_json()["loans"]
    assert len(cust2_loans) == 1
    assert cust2_loans[0]["id"] == loan2_id
    assert client.get(f"/api/loans/{loan1_id}").status_code == 403
    client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf2})

    # Employee (loan officer) sees all loans in the review queue and can inspect any loan
    client.post("/api/auth/login", json={"username": "emp1", "password": "EmpPass1"})
    emp_loans = client.get("/api/loans?status=pending").get_json()["loans"]
    assert len(emp_loans) == 2
    assert client.get(f"/api/loans/{loan1_id}").status_code == 200
    assert client.get(f"/api/loans/{loan2_id}").status_code == 200


def test_issue_12_loan_approval_and_rejection_workflow(client):
    """
    Issue #12: Loan officer (Employee/Admin) approves or rejects pending loans;
    customers are forbidden from making loan decisions; rejecting requires a non-blank reason;
    already decided loans cannot be re-decided.
    """
    # cust1 submits two loan applications
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf_cust = client.get("/api/auth/csrf").get_json()["csrf_token"]

    loan_a = client.post(
        "/api/loans",
        headers={"X-CSRF-Token": csrf_cust},
        json={"loan_type": "personal", "amount": "30000.00", "term_months": 12, "purpose": "Home renovation"},
    ).get_json()["loan"]

    loan_b = client.post(
        "/api/loans",
        headers={"X-CSRF-Token": csrf_cust},
        json={"loan_type": "business", "amount": "500000.00", "term_months": 60, "purpose": "Working capital"},
    ).get_json()["loan"]

    # Customer cannot approve their own loan (403 Forbidden)
    cust_decide = client.patch(
        f"/api/loans/{loan_a['id']}/decision",
        headers={"X-CSRF-Token": csrf_cust},
        json={"decision": "approved"},
    )
    assert cust_decide.status_code == 403
    client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf_cust})

    # Login as Employee (Loan Officer)
    client.post("/api/auth/login", json={"username": "emp1", "password": "EmpPass1"})
    csrf_emp = client.get("/api/auth/csrf").get_json()["csrf_token"]

    # 1. Approve loan_a
    approve_res = client.patch(
        f"/api/loans/{loan_a['id']}/decision",
        headers={"X-CSRF-Token": csrf_emp},
        json={"decision": "approved", "decision_notes": "Income and credit verified"},
    )
    assert approve_res.status_code == 200
    approved_loan = approve_res.get_json()["loan"]
    assert approved_loan["status"] == "approved"
    assert approved_loan["reviewer_username"] == "emp1"
    assert approved_loan["decision_notes"] == "Income and credit verified"
    assert approved_loan["reviewed_at"] is not None

    # 2. Rejecting loan_b without a rejection reason must fail with 400 (prevents Defect IT_09)
    reject_blank = client.patch(
        f"/api/loans/{loan_b['id']}/decision",
        headers={"X-CSRF-Token": csrf_emp},
        json={"decision": "rejected", "rejection_reason": "   "},
    )
    assert reject_blank.status_code == 400
    assert "Rejection reason is required" in reject_blank.get_json()["error"]

    # 3. Reject loan_b with a valid rejection reason
    reject_res = client.patch(
        f"/api/loans/{loan_b['id']}/decision",
        headers={"X-CSRF-Token": csrf_emp},
        json={"decision": "rejected", "rejection_reason": "Debt-to-income ratio exceeds policy limit"},
    )
    assert reject_res.status_code == 200
    rejected_loan = reject_res.get_json()["loan"]
    assert rejected_loan["status"] == "rejected"
    assert rejected_loan["rejection_reason"] == "Debt-to-income ratio exceeds policy limit"
    assert rejected_loan["reviewer_username"] == "emp1"

    # 4. Attempting to re-decide an already processed loan returns 400
    re_decide = client.patch(
        f"/api/loans/{loan_a['id']}/decision",
        headers={"X-CSRF-Token": csrf_emp},
        json={"decision": "rejected", "rejection_reason": "Changed mind"},
    )
    assert re_decide.status_code == 400
    assert "already been processed" in re_decide.get_json()["error"]


# ==============================================================================
# ISSUE #17: BENEFICIARY MANAGEMENT TESTS
# ==============================================================================
def test_issue_17_add_list_update_delete_beneficiary_success(client):
    """Issue #17: Customer can add, list, search, update, and remove a saved beneficiary."""
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]

    # 1. Add cust2's account (200000000001) as a beneficiary
    add_res = client.post(
        "/api/beneficiaries",
        headers={"X-CSRF-Token": csrf},
        json={
            "beneficiary_name": "Customer Two",
            "account_number": "200000000001",
            "nickname": "Partner",
            "max_transfer_limit": "500.00",
        },
    )
    assert add_res.status_code == 201
    ben = add_res.get_json()["beneficiary"]
    assert ben["beneficiary_name"] == "Customer Two"
    assert ben["account_number"] == "200000000001"
    assert ben["nickname"] == "Partner"
    assert ben["max_transfer_limit"] == "500.00"
    assert ben["max_transfer_limit_paise"] == 50000
    assert ben["is_verified"] is True
    ben_id = ben["id"]

    # 2. List and search beneficiaries
    list_res = client.get("/api/beneficiaries?search=partner")
    assert list_res.status_code == 200
    bens = list_res.get_json()["beneficiaries"]
    assert len(bens) == 1
    assert bens[0]["id"] == ben_id

    # 3. Update beneficiary nickname and limit
    patch_res = client.patch(
        f"/api/beneficiaries/{ben_id}",
        headers={"X-CSRF-Token": csrf},
        json={"nickname": "Trusted Partner", "max_transfer_limit": "800.00"},
    )
    assert patch_res.status_code == 200
    updated_ben = patch_res.get_json()["beneficiary"]
    assert updated_ben["nickname"] == "Trusted Partner"
    assert updated_ben["max_transfer_limit"] == "800.00"

    # 4. Delete beneficiary
    del_res = client.delete(f"/api/beneficiaries/{ben_id}", headers={"X-CSRF-Token": csrf})
    assert del_res.status_code == 200
    assert len(client.get("/api/beneficiaries").get_json()["beneficiaries"]) == 0


def test_issue_17_beneficiary_validation_and_duplicate_prevention(client):
    """Issue #17: Rejects self-beneficiary, non-existent accounts, invalid IFSC/limits, and duplicates."""
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]

    # Missing beneficiary name
    assert client.post(
        "/api/beneficiaries",
        headers={"X-CSRF-Token": csrf},
        json={"beneficiary_name": "  ", "account_number": "200000000001"},
    ).status_code == 400

    # Non-existent account number
    assert client.post(
        "/api/beneficiaries",
        headers={"X-CSRF-Token": csrf},
        json={"beneficiary_name": "Ghost User", "account_number": "999999999999"},
    ).status_code == 404

    # Adding own account as beneficiary must be blocked (400)
    self_ben = client.post(
        "/api/beneficiaries",
        headers={"X-CSRF-Token": csrf},
        json={"beneficiary_name": "My Own Account", "account_number": "100000000001"},
    )
    assert self_ben.status_code == 400
    assert "own account" in self_ben.get_json()["error"]

    # Invalid IFSC code format
    bad_ifsc = client.post(
        "/api/beneficiaries",
        headers={"X-CSRF-Token": csrf},
        json={"beneficiary_name": "Customer Two", "account_number": "200000000001", "ifsc_code": "BADIFSC"},
    )
    assert bad_ifsc.status_code == 400

    # Valid beneficiary creation followed by duplicate attempt (409 Conflict)
    ok_res = client.post(
        "/api/beneficiaries",
        headers={"X-CSRF-Token": csrf},
        json={"beneficiary_name": "Customer Two", "account_number": "200000000001"},
    )
    assert ok_res.status_code == 201

    dup_res = client.post(
        "/api/beneficiaries",
        headers={"X-CSRF-Token": csrf},
        json={"beneficiary_name": "Customer Two Duplicate", "account_number": "200000000001"},
    )
    assert dup_res.status_code == 409


def test_issue_17_beneficiary_ownership_isolation_and_transfer_integration(client):
    """
    Issue #17: Enforces RBAC ownership isolation across customers and supports transferring
    directly to a saved beneficiary while enforcing the configured max_transfer_limit.
    """
    client.post("/api/auth/login", json={"username": "cust1", "password": "CustPass1"})
    csrf1 = client.get("/api/auth/csrf").get_json()["csrf_token"]

    ben = client.post(
        "/api/beneficiaries",
        headers={"X-CSRF-Token": csrf1},
        json={
            "beneficiary_name": "Customer Two",
            "account_number": "200000000001",
            "max_transfer_limit": "400.00",
        },
    ).get_json()["beneficiary"]
    ben_id = ben["id"]

    # Transfer exceeding beneficiary max_transfer_limit (400.00) must be rejected
    over_limit = client.post(
        "/api/accounts/1/transfer",
        headers={"X-CSRF-Token": csrf1},
        json={"beneficiary_id": ben_id, "amount": "450.00", "description": "Over beneficiary limit"},
    )
    assert over_limit.status_code == 400
    assert "beneficiary limit" in over_limit.get_json()["error"]

    # Transfer within beneficiary max_transfer_limit succeeds using beneficiary_id
    ok_transfer = client.post(
        "/api/accounts/1/transfer",
        headers={"X-CSRF-Token": csrf1},
        json={"beneficiary_id": ben_id, "amount": "250.00", "description": "Beneficiary transfer"},
    )
    assert ok_transfer.status_code == 201
    assert ok_transfer.get_json()["transfer"]["destination_account_number"] == "200000000001"
    client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf1})

    # cust2 cannot access, modify, or delete cust1's beneficiary (403 Forbidden)
    client.post("/api/auth/login", json={"username": "cust2", "password": "CustPass2"})
    csrf2 = client.get("/api/auth/csrf").get_json()["csrf_token"]
    assert client.get(f"/api/beneficiaries/{ben_id}").status_code == 403
    assert client.patch(
        f"/api/beneficiaries/{ben_id}",
        headers={"X-CSRF-Token": csrf2},
        json={"nickname": "Hijacked"},
    ).status_code == 403
    assert client.delete(f"/api/beneficiaries/{ben_id}", headers={"X-CSRF-Token": csrf2}).status_code == 403
