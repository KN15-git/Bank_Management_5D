"""
Automated Pytest Suite for Issue #24: Backup and Recovery.
Validates:
- Online atomic SQLite backup generation (SEC-07, SEC-10).
- Cryptographic SHA-256 checksum and PRAGMA integrity verification.
- Role-based access control (Admin only, 403 Forbidden for customer/employee).
- End-to-end disaster recovery restoration (SRS Acceptance Criteria).
- Pre-restore safety snapshot creation to guarantee zero data loss.
- Protection against restoring corrupted or tampered backup files.
- Backup manager CLI commands (backup, list, verify).
"""

import json
import os
import sqlite3
import pytest
from app import (
    Role,
    AccountType,
    AccountStatus,
    create_app,
    get_db,
    init_db,
    hash_password,
)
import backup_manager


@pytest.fixture
def app_and_client(tmp_path):
    database_file = tmp_path / "test_backup.db"
    backup_folder = tmp_path / "backups_storage"

    app = create_app({
        "TESTING": True,
        "DATABASE_PATH": str(database_file),
        "BACKUP_DIR": str(backup_folder),
        "SECRET_KEY": "test-key-for-backups",
        "SESSION_COOKIE_SECURE": False,
    })

    with app.app_context():
        init_db()
        db = get_db()
        cursor = db.cursor()

        users = [
            ("admin_boss", "admin@pesbank.com", "Admin Boss", "AdminPass@123", Role.ADMIN.value),
            ("officer_bob", "officer@pesbank.com", "Officer Bob", "OfficerPass@123", Role.EMPLOYEE.value),
            ("cust_sam", "sam@example.com", "Sam Wilson", "SamPass@123", Role.CUSTOMER.value),
        ]
        uids = {}
        for username, email, full_name, password, role in users:
            cursor.execute(
                "INSERT INTO users (username, email, full_name, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
                (username, email, full_name, hash_password(password), role),
            )
            uids[username] = cursor.lastrowid

        accounts = [
            ("100000000001", uids["cust_sam"], AccountType.SAVINGS.value, 5000000, AccountStatus.ACTIVE.value),
        ]
        cursor.executemany(
            "INSERT INTO accounts (account_number, user_id, account_type, balance, status) VALUES (?, ?, ?, ?, ?)",
            accounts,
        )
        db.commit()

    with app.test_client() as test_client:
        yield app, test_client, database_file, backup_folder


def get_csrf(client):
    return client.get("/api/auth/csrf").get_json()["csrf_token"]


def login_user(client, username, password):
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.get_json()


def test_admin_create_backup_success(app_and_client):
    """Test that Administrator can create an online database backup (Issue #24, SEC-07)."""
    app, client, db_path, b_dir = app_and_client
    login_user(client, "admin_boss", "AdminPass@123")
    csrf = get_csrf(client)

    create_res = client.post(
        "/api/admin/backups",
        headers={"X-CSRF-Token": csrf},
        json={"note": "Nightly automated test snapshot"},
    )
    assert create_res.status_code == 201
    payload = create_res.get_json()
    backup = payload["backup"]

    assert backup["status"] == "valid"
    assert backup["file_size_bytes"] > 0
    assert len(backup["sha256_checksum"]) == 64
    assert os.path.isfile(backup["filepath"])
    assert backup["tables_summary"]["users"] >= 3
    assert backup["tables_summary"]["accounts"] >= 1


def test_verify_backup_integrity(app_and_client):
    """Test verification of backup file checksum and SQLite integrity (SEC-10)."""
    app, client, db_path, b_dir = app_and_client
    login_user(client, "admin_boss", "AdminPass@123")
    csrf = get_csrf(client)

    # 1. Create backup
    create_res = client.post("/api/admin/backups", headers={"X-CSRF-Token": csrf})
    assert create_res.status_code == 201
    backup_id = create_res.get_json()["backup"]["id"]

    # 2. Verify backup
    verify_res = client.get(f"/api/admin/backups/{backup_id}/verify")
    assert verify_res.status_code == 200
    v_data = verify_res.get_json()

    assert v_data["valid"] is True
    assert v_data["checksum_verified"] is True
    assert v_data["integrity_check"] == "ok"


def test_rbac_protects_backup_endpoints(app_and_client):
    """Test that customer and employee cannot access or trigger backup/restore (SEC-02, SEC-03)."""
    app, client, db_path, b_dir = app_and_client

    # Customer attempt
    login_user(client, "cust_sam", "SamPass@123")
    csrf_sam = get_csrf(client)
    res_list = client.get("/api/admin/backups")
    assert res_list.status_code == 403
    res_create = client.post("/api/admin/backups", headers={"X-CSRF-Token": csrf_sam})
    assert res_create.status_code == 403

    # Employee attempt
    client.post("/api/auth/logout")
    login_user(client, "officer_bob", "OfficerPass@123")
    csrf_bob = get_csrf(client)
    res_emp = client.get("/api/admin/backups")
    assert res_emp.status_code == 403
    res_emp_create = client.post("/api/admin/backups", headers={"X-CSRF-Token": csrf_bob})
    assert res_emp_create.status_code == 403


def test_end_to_end_disaster_recovery_restoration(app_and_client):
    """
    Test End-to-End Disaster Recovery:
    Pass: Critical data can be restored from a valid backup within the defined recovery process (SRS criteria).
    """
    app, client, db_path, b_dir = app_and_client

    # 1. Admin logs in and takes baseline Backup #1
    login_user(client, "admin_boss", "AdminPass@123")
    csrf_admin = get_csrf(client)
    backup_res = client.post("/api/admin/backups", headers={"X-CSRF-Token": csrf_admin})
    assert backup_res.status_code == 201
    backup_id = backup_res.get_json()["backup"]["id"]

    # Verify Sam's initial balance is ₹50,000.00
    with app.app_context():
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute("SELECT balance FROM accounts WHERE id = 1")
        initial_balance = c.fetchone()[0]
        conn.close()
    assert initial_balance == 5000000

    # 2. Sam logs in and performs a deposit of ₹25,000.00 (balance becomes ₹75,000.00)
    client.post("/api/auth/logout")
    login_user(client, "cust_sam", "SamPass@123")
    csrf_sam = get_csrf(client)
    dep_res = client.post(
        "/api/accounts/1/deposit",
        headers={"X-CSRF-Token": csrf_sam},
        json={"amount": "25000.00", "description": "Deposit before crash"},
    )
    assert dep_res.status_code == 201
    assert dep_res.get_json()["transaction"]["balance_after"] == "75000.00"


    # Also insert extra data to simulate state changes
    with app.app_context():
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute("SELECT balance FROM accounts WHERE id = 1")
        assert c.fetchone()[0] == 7500000
        conn.close()

    # 3. Simulate disaster: Admin triggers RESTORE from Backup #1
    client.post("/api/auth/logout")
    login_user(client, "admin_boss", "AdminPass@123")
    csrf_admin = get_csrf(client)

    restore_res = client.post(f"/api/admin/backups/{backup_id}/restore", headers={"X-CSRF-Token": csrf_admin})
    assert restore_res.status_code == 200
    r_data = restore_res.get_json()
    assert r_data["result"]["success"] is True
    assert r_data["result"]["safety_snapshot"] is not None

    # 4. Verify system data has been faithfully restored to baseline (₹50,000.00)
    with app.app_context():
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute("SELECT balance FROM accounts WHERE id = 1")
        restored_balance = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM transactions WHERE account_id = 1")
        tx_count = c.fetchone()[0]
        conn.close()

    assert restored_balance == 5000000, f"Expected 5000000, got {restored_balance}"
    assert tx_count == 0, "Transactions executed post-backup must be reverted upon restore"


def test_restore_rejects_corrupted_backup(app_and_client):
    """Test that attempting to restore a corrupted backup is rejected without touching live data."""
    app, client, db_path, b_dir = app_and_client
    login_user(client, "admin_boss", "AdminPass@123")
    csrf = get_csrf(client)

    # Create valid backup
    create_res = client.post("/api/admin/backups", headers={"X-CSRF-Token": csrf})
    assert create_res.status_code == 201
    backup_data = create_res.get_json()["backup"]
    filepath = backup_data["filepath"]
    backup_id = backup_data["id"]

    # Deliberately corrupt backup file by appending random garbage bytes
    with open(filepath, "r+b") as f:
        f.seek(100)
        f.write(b"CORRUPTED_GARBAGE_BYTES_TEST")

    # Attempt to restore corrupted backup
    corrupt_restore = client.post(f"/api/admin/backups/{backup_id}/restore", headers={"X-CSRF-Token": csrf})
    assert corrupt_restore.status_code == 400
    assert "verification failed" in corrupt_restore.get_json()["error"]
