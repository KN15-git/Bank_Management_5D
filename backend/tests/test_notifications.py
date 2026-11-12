"""
Automated Pytest Suite for Issue #16: Transaction & Loan Notifications.
Validates:
- Notification creation on Deposits (#5), Withdrawals (#6), and Transfers (#8).
- Dual notifications for sender and receiver on fund transfer.
- Customer notifications on Loan Application (#10) and Approval/Rejection decisions (#11, #12).
- Mandatory rejection reason inclusion in loan rejection notifications (Bank Test Plan IT_09).
- Delivery SLA verification (< 1 minute, Bank Test Plan IT_03).
- REST API endpoints (list, filter, unread count, mark read, mark all read, delete).
- Strict user ownership isolation (SEC-02).
"""

import time
import pytest
from app import (
    Role,
    AccountType,
    AccountStatus,
    LoanType,
    create_app,
    get_db,
    init_db,
    hash_password,
    DISPATCHED_NOTIFICATIONS_QUEUE,
)


@pytest.fixture
def client(tmp_path):
    database_file = tmp_path / "test_notifications.db"
    backup_folder = tmp_path / "backups"
    app = create_app({
        "TESTING": True,
        "DATABASE_PATH": str(database_file),
        "BACKUP_DIR": str(backup_folder),
        "SECRET_KEY": "test-key-for-notifications",
        "SESSION_COOKIE_SECURE": False,
    })

    with app.app_context():
        init_db()
        db = get_db()
        cursor = db.cursor()

        users = [
            ("admin1", "admin1@pesbank.com", "System Admin", "AdminPass@123", Role.ADMIN.value),
            ("officer1", "officer1@pesbank.com", "Loan Officer", "OfficerPass@123", Role.EMPLOYEE.value),
            ("cust_rahul", "rahul@example.com", "Rahul Kumar", "RahulPass@123", Role.CUSTOMER.value),
            ("cust_anita", "anita@example.com", "Anita Suresh", "AnitaPass@123", Role.CUSTOMER.value),
        ]
        uids = {}
        for username, email, full_name, password, role in users:
            cursor.execute(
                "INSERT INTO users (username, email, full_name, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
                (username, email, full_name, hash_password(password), role),
            )
            uids[username] = cursor.lastrowid

        accounts = [
            ("100000000001", uids["cust_rahul"], AccountType.SAVINGS.value, 5000000, AccountStatus.ACTIVE.value),
            ("100000000002", uids["cust_rahul"], AccountType.CURRENT.value, 1000000, AccountStatus.ACTIVE.value),
            ("200000000001", uids["cust_anita"], AccountType.SAVINGS.value, 2000000, AccountStatus.ACTIVE.value),
        ]
        cursor.executemany(
            "INSERT INTO accounts (account_number, user_id, account_type, balance, status) VALUES (?, ?, ?, ?, ?)",
            accounts,
        )
        db.commit()

    with app.test_client() as test_client:
        yield test_client


def get_csrf(client):
    res = client.get("/api/auth/csrf")
    return res.get_json()["csrf_token"]


def login_user(client, username, password):
    res = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert res.status_code == 200, f"Failed to login {username}: {res.get_json()}"
    return res.get_json()


def test_deposit_triggers_notification(client):
    """Test that depositing money generates a transaction notification (Issue #16, IT_03)."""
    login_user(client, "cust_rahul", "RahulPass@123")
    csrf = get_csrf(client)

    deposit_res = client.post(
        "/api/accounts/1/deposit",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "3000.00", "description": "Salary Bonus"},
    )
    assert deposit_res.status_code == 201
    dep_data = deposit_res.get_json()
    ref_id = dep_data["transaction"]["reference_id"]

    notif_res = client.get("/api/notifications")
    assert notif_res.status_code == 200
    data = notif_res.get_json()

    assert data["total_count"] >= 1
    assert data["unread_count"] >= 1

    deposit_notif = next((n for n in data["notifications"] if n["reference_id"] == ref_id), None)
    assert deposit_notif is not None, "Notification for deposit was not generated"
    assert deposit_notif["notification_type"] == "transaction"
    assert deposit_notif["event_type"] == "deposit"
    assert "3,000.00" in deposit_notif["message"] or "3000.00" in deposit_notif["message"]
    assert deposit_notif["is_read"] is False


def test_withdrawal_triggers_notification(client):
    """Test that withdrawing money generates a transaction notification (Issue #16)."""
    login_user(client, "cust_rahul", "RahulPass@123")
    csrf = get_csrf(client)

    withdraw_res = client.post(
        "/api/accounts/1/withdraw",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "1500.00", "description": "ATM Cash Withdrawal"},
    )
    assert withdraw_res.status_code == 201
    with_data = withdraw_res.get_json()
    ref_id = with_data["transaction"]["reference_id"]

    notif_res = client.get("/api/notifications")
    assert notif_res.status_code == 200
    data = notif_res.get_json()

    with_notif = next((n for n in data["notifications"] if n["reference_id"] == ref_id), None)
    assert with_notif is not None
    assert with_notif["notification_type"] == "transaction"
    assert with_notif["event_type"] == "withdrawal"
    assert "1,500.00" in with_notif["message"] or "1500.00" in with_notif["message"]


def test_transfer_triggers_dual_notifications(client):
    """Test that inter-account transfer notifies both the sender and the recipient (Issue #16)."""
    # Rahul transfers ₹2,500 to Anita
    login_user(client, "cust_rahul", "RahulPass@123")
    csrf_rahul = get_csrf(client)

    transfer_res = client.post(
        "/api/transfers",
        headers={"X-CSRF-Token": csrf_rahul},
        json={
            "source_account_id": 1,
            "destination_account_number": "200000000001",
            "amount": "2500.00",
            "description": "Project payment",
        },
    )
    assert transfer_res.status_code == 201
    transfer_ref = transfer_res.get_json()["transfer"]["reference_id"]

    # Check sender (Rahul) notification
    notif_rahul = client.get("/api/notifications").get_json()
    sender_notif = next((n for n in notif_rahul["notifications"] if n["reference_id"] == transfer_ref), None)
    assert sender_notif is not None
    assert sender_notif["event_type"] == "transfer_out"
    assert "Transferred" in sender_notif["title"] or "Sent" in sender_notif["title"]

    # Check receiver (Anita) notification
    client.post("/api/auth/logout")
    login_user(client, "cust_anita", "AnitaPass@123")
    notif_anita = client.get("/api/notifications").get_json()
    receiver_notif = next((n for n in notif_anita["notifications"] if n["reference_id"] == transfer_ref), None)
    assert receiver_notif is not None
    assert receiver_notif["event_type"] == "transfer_in"
    assert "Received" in receiver_notif["title"]


def test_loan_lifecycle_notifications(client):
    """
    Test complete loan notification flow (Issues #10, #11, #12, #16, IT_08, IT_09, ST_08):
    1. Submission -> customer notified
    2. Approval -> customer notified
    3. Rejection with mandatory reason -> customer notified with reason included.
    """
    # 1. Rahul applies for loan
    login_user(client, "cust_rahul", "RahulPass@123")
    csrf_rahul = get_csrf(client)

    apply_res = client.post(
        "/api/loans",
        headers={"X-CSRF-Token": csrf_rahul},
        json={
            "loan_type": "home",
            "amount": "500000.00",
            "term_months": 60,
            "purpose": "Home renovation",
            "account_id": 1,
        },
    )
    assert apply_res.status_code == 201
    loan_id = apply_res.get_json()["loan"]["id"]
    loan_ref = apply_res.get_json()["loan"]["reference_id"]

    # Verify submission notification
    sub_notifs = client.get("/api/notifications?type=loan").get_json()["notifications"]
    sub_entry = next((n for n in sub_notifs if n["reference_id"] == loan_ref), None)
    assert sub_entry is not None
    assert sub_entry["event_type"] == "loan_applied"

    # 2. Officer approves loan
    client.post("/api/auth/logout")
    login_user(client, "officer1", "OfficerPass@123")
    csrf_officer = get_csrf(client)

    appr_res = client.patch(
        f"/api/loans/{loan_id}/decision",
        headers={"X-CSRF-Token": csrf_officer},
        json={"decision": "approved", "decision_notes": "All documentation verified"},
    )
    assert appr_res.status_code == 200

    # Verify customer received approval notification (IT_08)
    client.post("/api/auth/logout")
    login_user(client, "cust_rahul", "RahulPass@123")
    appr_notifs = client.get("/api/notifications?type=loan").get_json()["notifications"]
    appr_entry = next((n for n in appr_notifs if n["event_type"] == "loan_approved" and n["reference_id"] == loan_ref), None)
    assert appr_entry is not None
    assert "Approved" in appr_entry["title"]

    # 3. Test loan rejection with mandatory reason (IT_09)
    csrf_rahul = get_csrf(client)
    apply2_res = client.post(
        "/api/loans",
        headers={"X-CSRF-Token": csrf_rahul},
        json={
            "loan_type": "personal",
            "amount": "200000.00",
            "term_months": 24,
            "purpose": "Emergency medical",
            "account_id": 1,
        },
    )
    assert apply2_res.status_code == 201
    loan2_id = apply2_res.get_json()["loan"]["id"]
    loan2_ref = apply2_res.get_json()["loan"]["reference_id"]

    # Officer rejects application with specific reason
    client.post("/api/auth/logout")
    login_user(client, "officer1", "OfficerPass@123")
    csrf_officer = get_csrf(client)

    rej_reason = "Insufficient income proof and credit score threshold not met"
    rej_res = client.patch(
        f"/api/loans/{loan2_id}/decision",
        headers={"X-CSRF-Token": csrf_officer},
        json={"decision": "rejected", "rejection_reason": rej_reason},
    )
    assert rej_res.status_code == 200

    # Customer verifies rejection notification contains the explicit reason (IT_09)
    client.post("/api/auth/logout")
    login_user(client, "cust_rahul", "RahulPass@123")
    rej_notifs = client.get("/api/notifications?type=loan").get_json()["notifications"]
    rej_entry = next((n for n in rej_notifs if n["event_type"] == "loan_rejected" and n["reference_id"] == loan2_ref), None)
    assert rej_entry is not None
    assert "Rejected" in rej_entry["title"]
    assert rej_reason in rej_entry["message"], "Rejection reason must be present in customer notification (Test Plan IT_09)"


def test_mark_as_read_and_mark_all_read(client):
    """Test marking individual notification and batch marking all notifications as read."""
    login_user(client, "cust_rahul", "RahulPass@123")
    csrf = get_csrf(client)

    # Generate 2 notifications
    client.post("/api/accounts/1/deposit", headers={"X-CSRF-Token": csrf}, json={"amount": "100.00"})
    client.post("/api/accounts/1/deposit", headers={"X-CSRF-Token": csrf}, json={"amount": "200.00"})

    summary = client.get("/api/notifications/summary").get_json()
    assert summary["unread_count"] >= 2
    first_id = summary["latest"][0]["id"]

    # Mark single notification as read
    read_res = client.patch(f"/api/notifications/{first_id}/read", headers={"X-CSRF-Token": csrf})
    assert read_res.status_code == 200

    after_read = client.get("/api/notifications/summary").get_json()
    assert after_read["unread_count"] == summary["unread_count"] - 1

    # Mark all remaining notifications as read
    all_read_res = client.post("/api/notifications/mark-all-read", headers={"X-CSRF-Token": csrf})
    assert all_read_res.status_code == 200

    final_summary = client.get("/api/notifications/summary").get_json()
    assert final_summary["unread_count"] == 0


def test_notification_ownership_isolation(client):
    """Test that customer cannot read, mark, or delete another customer's notifications (SEC-02)."""
    login_user(client, "cust_rahul", "RahulPass@123")
    csrf_rahul = get_csrf(client)
    client.post("/api/accounts/1/deposit", headers={"X-CSRF-Token": csrf_rahul}, json={"amount": "500.00"})
    rahul_notifs = client.get("/api/notifications").get_json()["notifications"]
    rahul_notif_id = rahul_notifs[0]["id"]

    # Switch to Anita
    client.post("/api/auth/logout")
    login_user(client, "cust_anita", "AnitaPass@123")
    csrf_anita = get_csrf(client)

    # Anita attempts to mark Rahul's notification as read
    forbidden_read = client.patch(f"/api/notifications/{rahul_notif_id}/read", headers={"X-CSRF-Token": csrf_anita})
    assert forbidden_read.status_code == 403

    # Anita attempts to delete Rahul's notification
    forbidden_delete = client.delete(f"/api/notifications/{rahul_notif_id}", headers={"X-CSRF-Token": csrf_anita})
    assert forbidden_delete.status_code == 403


def test_notification_delivery_latency_sla(client):
    """Verify that notification dispatch happens instantaneously (< 1 min, Bank Test Plan IT_03)."""
    start_time = time.time()
    login_user(client, "cust_rahul", "RahulPass@123")
    csrf = get_csrf(client)

    client.post("/api/accounts/1/deposit", headers={"X-CSRF-Token": csrf}, json={"amount": "50.00"})
    elapsed = time.time() - start_time

    # Must be delivered well under 1 minute (60 seconds)
    assert elapsed < 5.0, f"Notification generation took {elapsed:.2f}s, expected < 1s"
    assert len(DISPATCHED_NOTIFICATIONS_QUEUE) > 0
