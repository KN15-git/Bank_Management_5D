import time
"""
PES University Bank Management System - Flask REST API Backend
Implements:
- Issue #2: Authentication and Login
- Issue #3: Role-Based Access Control
- Issue #4: Account and Balance Management
- Issue #5: Deposit Money
- Issue #6: Withdraw Money
- Issue #7: Transaction Validation & Recording
- Issue #8: Fund Transfer Between Accounts
- Issue #9: Atomic Transfer & Rollback
"""
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps

import bcrypt
from dotenv import load_dotenv
from flask import Flask, Blueprint, request, jsonify, session, g, current_app
from flask_cors import CORS
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    current_user,
    login_required,
)

load_dotenv()

# ==============================================================================
# 1. CONSTANTS & ENUMS (#3, #4, #5, #6, #7, #8, #9)
# ==============================================================================
class Role(str, Enum):
    CUSTOMER = "customer"
    EMPLOYEE = "employee"
    ADMIN = "admin"

    @classmethod
    def all_roles(cls):
        return [cls.CUSTOMER.value, cls.EMPLOYEE.value, cls.ADMIN.value]


class AccountStatus(str, Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


class AccountType(str, Enum):
    SAVINGS = "savings"
    CURRENT = "current"


class TransactionType(str, Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER_OUT = "transfer_out"
    TRANSFER_IN = "transfer_in"


# ==============================================================================
# 2. USER MODEL & DATABASE HELPERS
# ==============================================================================
class User(UserMixin):
    def __init__(self, id, username, email, full_name, role, is_active=True):
        self.id = id
        self.username = username
        self.email = email
        self.full_name = full_name
        self.role = role
        self._is_active = bool(is_active)

    @property
    def is_active(self):
        return self._is_active

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
        }


def get_db():
    """Return a per-request SQLite connection with foreign keys enabled."""
    if "db" not in g:
        db_path = current_app.config.get("DATABASE_PATH", "bank.db")
        g.db = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db


def close_db(e=None):
    """Close the database connection at the end of the request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app=None):
    """Initialize SQLite database using schema.sql and migrate older schemas if needed."""
    def _run():
        db = get_db()
        schema_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
        with open(schema_file, "r", encoding="utf-8") as f:
            db.executescript(f.read())

        # Migrate existing transactions table if it lacks transfer_out / transfer_in in CHECK constraint
        cursor = db.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='transactions'")
        row = cursor.fetchone()
        if row and row["sql"] and "transfer_out" not in row["sql"]:
            db.execute("PRAGMA foreign_keys = OFF;")
            db.executescript(
                """
                BEGIN TRANSACTION;
                CREATE TABLE transactions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference_id TEXT UNIQUE NOT NULL,
                    account_id INTEGER NOT NULL,
                    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('deposit', 'withdrawal', 'transfer_out', 'transfer_in')),
                    amount INTEGER NOT NULL CHECK (amount > 0),
                    balance_after INTEGER NOT NULL CHECK (balance_after >= 0),
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (account_id) REFERENCES accounts (id) ON DELETE RESTRICT
                );
                INSERT INTO transactions_new (id, reference_id, account_id, transaction_type, amount, balance_after, description, created_at)
                SELECT id, reference_id, account_id, transaction_type, amount, balance_after, description, created_at FROM transactions;
                DROP TABLE transactions;
                ALTER TABLE transactions_new RENAME TO transactions;
                CREATE INDEX IF NOT EXISTS idx_transactions_account_id ON transactions(account_id);
                CREATE INDEX IF NOT EXISTS idx_transactions_reference_id ON transactions(reference_id);
                COMMIT;
                """
            )
            db.execute("PRAGMA foreign_keys = ON;")

        db.commit()

    if app:
        with app.app_context():
            _run()
    else:
        _run()


# ==============================================================================
# 3. AUDIT & SECURITY UTILITIES
# ==============================================================================
def log_event(action: str, user_id=None, details: str = None, ip_address: str = None):
    """Record security and account lifecycle events to audit_logs."""
    if ip_address is None:
        try:
            ip_address = request.remote_addr
        except RuntimeError:
            ip_address = "system"

    db = get_db()
    db.execute(
        "INSERT INTO audit_logs (user_id, action, details, ip_address) VALUES (?, ?, ?, ?)",
        (user_id, action, details, ip_address),
    )
    db.commit()


def hash_password(password: str) -> str:
    """Hash plaintext password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password: str, password_hash: str) -> bool:
    """Verify password against bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def validate_password_policy(password: str) -> tuple[bool, str]:
    """Basic password policy: min length 8, at least one letter and one digit."""
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"[A-Za-z]", password):
        return False, "Password must contain at least one letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"
    return True, ""


def generate_csrf_token() -> str:
    """Generate or retrieve the session CSRF token."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def verify_csrf_token():
    """
    CSRF Protection (Synchronizer Token Pattern):
    State-changing requests (POST, PUT, PATCH, DELETE) require a matching X-CSRF-Token header.
    Public initial endpoints (login, register) are exempt.
    """
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        if request.endpoint in ["auth.login", "auth.register"]:
            return None
        token = request.headers.get("X-CSRF-Token")
        expected = session.get("csrf_token")
        if not expected or not token or not secrets.compare_digest(token, expected):
            return jsonify({"error": "Invalid or missing CSRF token"}), 403
    return None


# ==============================================================================
# 4. RBAC & OWNERSHIP HELPERS
# ==============================================================================
def role_required(*allowed_roles):
    """Decorator to enforce role permissions on API routes."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"error": "Authentication required"}), 401
            if current_user.role not in allowed_roles:
                log_event(
                    "ACCESS_DENIED",
                    user_id=current_user.id,
                    details=f"Allowed: {allowed_roles}, User role: {current_user.role}",
                )
                return jsonify({"error": "Access forbidden: insufficient permissions"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def assert_can_access_account(user, account_row) -> tuple[bool, int, str]:
    """
    Ownership enforcement assertion:
    Customer can only access their own accounts; Employee and Admin can access any.
    Returns 403 Forbidden to clearly indicate authorization boundary failure.
    """
    if user.role in [Role.ADMIN.value, Role.EMPLOYEE.value]:
        return True, 200, ""
    if account_row["user_id"] == user.id:
        return True, 200, ""

    log_event(
        "UNAUTHORIZED_ACCOUNT_ACCESS_ATTEMPT",
        user_id=user.id,
        details=f"Customer tried accessing account_id {account_row['id']} owned by {account_row['user_id']}",
    )
    return False, 403, "Access forbidden: you do not own this account"


# ==============================================================================
# 5. BUSINESS LOGIC SERVICES
# ==============================================================================
def get_user_by_id(user_id: int):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, username, email, full_name, role, is_active FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        return User(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            full_name=row["full_name"],
            role=row["role"],
            is_active=row["is_active"],
        )
    return None


def register_user(username: str, email: str, full_name: str, password: str):
    """Self-registration creates customer role only (#2)."""
    username = (username or "").strip().lower()
    email = (email or "").strip().lower()
    full_name = (full_name or "").strip()

    if not username or not email or not full_name or not password:
        return None, "All fields (username, email, full_name, password) are required", 400

    if len(username) < 3 or len(username) > 30:
        return None, "Username must be between 3 and 30 characters", 400

    valid_pw, pw_err = validate_password_policy(password)
    if not valid_pw:
        return None, pw_err, 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
    if cursor.fetchone():
        return None, "Username or email is already registered", 409

    hashed_pw = hash_password(password)
    try:
        cursor.execute(
            """
            INSERT INTO users (username, email, full_name, password_hash, role, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (username, email, full_name, hashed_pw, Role.CUSTOMER.value),
        )
        new_id = cursor.lastrowid
        db.commit()
    except Exception as e:
        db.rollback()
        return None, f"Database error: {str(e)}", 500

    log_event("USER_REGISTERED", user_id=new_id, details=f"Registered username: {username}")
    return get_user_by_id(new_id).to_dict(), None, 201


def authenticate_user(login_id: str, password: str):
    """Authenticate credentials with brute-force lockout protection (#2)."""
    login_id = (login_id or "").strip().lower()
    if not login_id or not password:
        return None, "Invalid credentials", 401

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT id, username, email, full_name, password_hash, role, is_active,
               failed_login_attempts, locked_until
        FROM users
        WHERE username = ? OR email = ?
        """,
        (login_id, login_id),
    )
    user_row = cursor.fetchone()
    now_utc = datetime.now(timezone.utc)

    if not user_row:
        check_password(password, "$2b$12$e8YVz2y1i.74oJ3B8jLhXeWj1K9Fj8a7kL9hN4VzR1eG6a5nC4r7e")
        log_event("LOGIN_FAILED", details=f"Non-existent login: {login_id}")
        return None, "Invalid credentials", 401

    user_id = user_row["id"]

    locked_until_str = user_row["locked_until"]
    if locked_until_str:
        try:
            locked_dt = (
                locked_until_str
                if isinstance(locked_until_str, datetime)
                else datetime.fromisoformat(locked_until_str)
            )
            if locked_dt.tzinfo is None:
                locked_dt = locked_dt.replace(tzinfo=timezone.utc)

            if now_utc < locked_dt:
                log_event("LOGIN_BLOCKED_LOCKOUT", user_id=user_id, details="Attempt while locked")
                return None, "Account is temporarily locked due to multiple failed logins. Please try again later.", 403
            else:
                cursor.execute(
                    "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = ?",
                    (user_id,),
                )
                db.commit()
        except Exception:
            pass

    if not user_row["is_active"]:
        log_event("LOGIN_FAILED_INACTIVE", user_id=user_id, details="Inactive user login attempt")
        return None, "Account has been deactivated. Please contact bank administration.", 403

    if not check_password(password, user_row["password_hash"]):
        failed_count = user_row["failed_login_attempts"] + 1
        if failed_count >= 5:
            lock_until_val = now_utc + timedelta(minutes=15)
            cursor.execute(
                "UPDATE users SET failed_login_attempts = ?, locked_until = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (failed_count, lock_until_val.isoformat(), user_id),
            )
            db.commit()
            log_event("ACCOUNT_LOCKED", user_id=user_id, details=f"Locked after {failed_count} failures")
            return None, "Account is temporarily locked due to multiple failed logins. Please try again later.", 403
        else:
            cursor.execute(
                "UPDATE users SET failed_login_attempts = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (failed_count, user_id),
            )
            db.commit()
            log_event("LOGIN_FAILED", user_id=user_id, details=f"Failed attempt {failed_count}/5")
            return None, "Invalid credentials", 401

    cursor.execute(
        "UPDATE users SET failed_login_attempts = 0, locked_until = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (user_id,),
    )
    db.commit()
    log_event("LOGIN_SUCCESS", user_id=user_id, details=f"User {user_row['username']} logged in")

    return (
        User(
            id=user_row["id"],
            username=user_row["username"],
            email=user_row["email"],
            full_name=user_row["full_name"],
            role=user_row["role"],
            is_active=user_row["is_active"],
        ),
        None,
        200,
    )


def paise_to_rupees_str(paise: int) -> str:
    """Format paise integer to decimal rupee string."""
    sign = "-" if paise < 0 else ""
    abs_val = abs(paise)
    return f"{sign}{abs_val // 100}.{abs_val % 100:02d}"


def rupees_to_paise(rupees_val) -> int:
    """Convert rupee value to integer paise without floating point issues."""
    if isinstance(rupees_val, int):
        return rupees_val * 100
    s = str(rupees_val).strip()
    if not s:
        return 0
    if "." in s:
        parts = s.split(".")
        if len(parts) > 2:
            raise ValueError("Invalid currency format")
        whole = int(parts[0]) if parts[0] else 0
        frac = int((parts[1] + "00")[:2])
        return whole * 100 + frac
    return int(s) * 100


def generate_unique_account_number() -> str:
    """Generate unique 12-digit account number."""
    db = get_db()
    cursor = db.cursor()
    while True:
        num = f"{secrets.randbelow(900000) + 100000}{secrets.randbelow(900000) + 100000}"
        cursor.execute("SELECT id FROM accounts WHERE account_number = ?", (num,))
        if not cursor.fetchone():
            return num


def generate_transaction_reference() -> str:
    """Generate unique alphanumeric transaction reference (e.g. TXN987654321012)."""
    db = get_db()
    cursor = db.cursor()
    while True:
        ref = f"TXN{secrets.token_hex(6).upper()}"
        cursor.execute("SELECT id FROM transactions WHERE reference_id = ?", (ref,))
        if not cursor.fetchone():
            cursor.execute("SELECT id FROM transfers WHERE reference_id = ?", (ref,))
            if not cursor.fetchone():
                return ref


def create_account(creator_user, user_id: int, account_type: str, initial_deposit_rupees: str = "0.00"):
    """Create account (#4). Customer can create savings for self; Employee/Admin for any user."""
    if creator_user.role == Role.CUSTOMER.value:
        if user_id != creator_user.id:
            return None, "Customers can only open accounts for themselves", 403
        if account_type != AccountType.SAVINGS.value:
            return None, "Customers can only open savings accounts online", 400

    if account_type not in [AccountType.SAVINGS.value, AccountType.CURRENT.value]:
        return None, "Invalid account_type. Allowed: savings, current", 400

    try:
        initial_paise = rupees_to_paise(initial_deposit_rupees)
    except ValueError:
        return None, "Invalid initial deposit amount format", 400

    if initial_paise < 0:
        return None, "Initial deposit cannot be negative", 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, username, is_active FROM users WHERE id = ?", (user_id,))
    target = cursor.fetchone()
    if not target:
        return None, "User does not exist", 404
    if not target["is_active"]:
        return None, "Cannot open account for an inactive user", 400

    acc_num = generate_unique_account_number()
    try:
        cursor.execute(
            """
            INSERT INTO accounts (account_number, user_id, account_type, balance, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (acc_num, user_id, account_type, initial_paise, AccountStatus.ACTIVE.value),
        )
        acc_id = cursor.lastrowid

        # If opening with initial deposit > 0, record initial deposit transaction (#7)
        if initial_paise > 0:
            ref_id = generate_transaction_reference()
            cursor.execute(
                """
                INSERT INTO transactions (reference_id, account_id, transaction_type, amount, balance_after, description)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ref_id, acc_id, TransactionType.DEPOSIT.value, initial_paise, initial_paise, "Initial account opening deposit"),
            )

        db.commit()
    except Exception as e:
        db.rollback()
        return None, f"Database error creating account: {str(e)}", 500

    log_event(
        "ACCOUNT_CREATED",
        user_id=creator_user.id,
        details=f"Created account {acc_num} ({account_type}) for user_id {user_id}",
    )
    return get_account_by_id(creator_user, acc_id)[0], None, 201


def get_accounts(user, search_query: str = None):
    """List accounts (#4). Customer sees own; Employee/Admin sees all."""
    db = get_db()
    cursor = db.cursor()
    if user.role == Role.CUSTOMER.value:
        cursor.execute(
            """
            SELECT a.id, a.account_number, a.user_id, a.account_type, a.balance, a.status,
                   a.created_at, a.updated_at, u.username, u.full_name, u.email
            FROM accounts a JOIN users u ON a.user_id = u.id
            WHERE a.user_id = ? ORDER BY a.id DESC
            """,
            (user.id,),
        )
    else:
        if search_query:
            term = f"%{search_query.strip().lower()}%"
            cursor.execute(
                """
                SELECT a.id, a.account_number, a.user_id, a.account_type, a.balance, a.status,
                       a.created_at, a.updated_at, u.username, u.full_name, u.email
                FROM accounts a JOIN users u ON a.user_id = u.id
                WHERE LOWER(a.account_number) LIKE ? OR LOWER(u.username) LIKE ? OR LOWER(u.full_name) LIKE ? OR LOWER(u.email) LIKE ?
                ORDER BY a.id DESC
                """,
                (term, term, term, term),
            )
        else:
            cursor.execute(
                """
                SELECT a.id, a.account_number, a.user_id, a.account_type, a.balance, a.status,
                       a.created_at, a.updated_at, u.username, u.full_name, u.email
                FROM accounts a JOIN users u ON a.user_id = u.id
                ORDER BY a.id DESC
                """
            )
    rows = cursor.fetchall()
    return [
        {
            "id": r["id"],
            "account_number": r["account_number"],
            "user_id": r["user_id"],
            "owner_username": r["username"],
            "owner_name": r["full_name"],
            "owner_email": r["email"],
            "account_type": r["account_type"],
            "balance_paise": r["balance"],
            "balance": paise_to_rupees_str(r["balance"]),
            "status": r["status"],
            "created_at": str(r["created_at"]),
            "updated_at": str(r["updated_at"]),
        }
        for r in rows
    ]


def get_account_by_id(user, account_id: int):
    """Retrieve single account with ownership assertion (#4)."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT a.id, a.account_number, a.user_id, a.account_type, a.balance, a.status,
               a.created_at, a.updated_at, u.username, u.full_name, u.email
        FROM accounts a JOIN users u ON a.user_id = u.id
        WHERE a.id = ?
        """,
        (account_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None, "Account not found", 404

    can_access, err_code, err_msg = assert_can_access_account(user, row)
    if not can_access:
        return None, err_msg, err_code

    return {
        "id": row["id"],
        "account_number": row["account_number"],
        "user_id": row["user_id"],
        "owner_username": row["username"],
        "owner_name": row["full_name"],
        "owner_email": row["email"],
        "account_type": row["account_type"],
        "balance_paise": row["balance"],
        "balance": paise_to_rupees_str(row["balance"]),
        "status": row["status"],
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }, None, 200


def update_account_status(user, account_id: int, new_status: str):
    """Update status (active, frozen, closed). Closing requires zero balance (#4)."""
    if user.role not in [Role.ADMIN.value, Role.EMPLOYEE.value]:
        return None, "Access forbidden: only employees and administrators can modify account status", 403

    valid_statuses = [AccountStatus.ACTIVE.value, AccountStatus.FROZEN.value, AccountStatus.CLOSED.value]
    if new_status not in valid_statuses:
        return None, f"Invalid status. Allowed statuses: {', '.join(valid_statuses)}", 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, account_number, balance, status FROM accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()
    if not row:
        return None, "Account not found", 404

    if new_status == AccountStatus.CLOSED.value and row["balance"] != 0:
        return (
            None,
            f"Cannot close account with non-zero balance (current balance: ₹{paise_to_rupees_str(row['balance'])}). Balance must be zero before closing.",
            400,
        )

    cursor.execute("UPDATE accounts SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, account_id))
    db.commit()

    log_event(
        "ACCOUNT_STATUS_CHANGED",
        user_id=user.id,
        details=f"Account {row['account_number']} changed from {row['status']} to {new_status}",
    )
    return {"id": account_id, "account_number": row["account_number"], "status": new_status}, None, 200


# ==============================================================================
# 5B. FINANCIAL TRANSACTIONS SERVICES (#5, #6, #7, #8, #9)
# ==============================================================================
def execute_deposit(user, account_id: int, amount_rupees: str, description: str = None):
    """
    Issue #5: Deposit money into active account.
    Issue #7: Validates and records transaction with reference_id and balance_after.
    """
    try:
        amount_paise = rupees_to_paise(amount_rupees)
    except ValueError:
        return None, "Invalid deposit amount format", 400

    if amount_paise <= 0:
        return None, "Enter a valid amount. Deposit amount must be greater than zero.", 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, account_number, user_id, balance, status FROM accounts WHERE id = ?",
        (account_id,),
    )
    acc = cursor.fetchone()
    if not acc:
        return None, "Account not found", 404

    can_access, err_code, err_msg = assert_can_access_account(user, acc)
    if not can_access:
        return None, err_msg, err_code

    if acc["status"] == AccountStatus.FROZEN.value:
        return None, "Account is frozen. Transactions are temporarily suspended.", 403
    if acc["status"] == AccountStatus.CLOSED.value:
        return None, "Cannot perform transactions on a closed account.", 400

    new_balance = acc["balance"] + amount_paise
    ref_id = generate_transaction_reference()
    desc = (description or "").strip() or "Cash/Online Deposit"

    try:
        cursor.execute("BEGIN TRANSACTION")
        cursor.execute(
            "UPDATE accounts SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_balance, account_id),
        )
        cursor.execute(
            """
            INSERT INTO transactions (reference_id, account_id, transaction_type, amount, balance_after, description)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ref_id, account_id, TransactionType.DEPOSIT.value, amount_paise, new_balance, desc),
        )
        txn_id = cursor.lastrowid
        db.commit()
    except Exception as e:
        db.rollback()
        return None, f"Transaction failed: {str(e)}", 500

    log_event(
        "DEPOSIT_PROCESSED",
        user_id=user.id,
        details=f"Deposited ₹{paise_to_rupees_str(amount_paise)} to account {acc['account_number']} (Ref: {ref_id})",
    )

    return {
        "transaction_id": txn_id,
        "reference_id": ref_id,
        "account_id": account_id,
        "account_number": acc["account_number"],
        "transaction_type": TransactionType.DEPOSIT.value,
        "amount": paise_to_rupees_str(amount_paise),
        "amount_paise": amount_paise,
        "balance_after": paise_to_rupees_str(new_balance),
        "balance_after_paise": new_balance,
        "description": desc,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, None, 201


def execute_withdrawal(user, account_id: int, amount_rupees: str, description: str = None):
    """
    Issue #6: Withdraw money with available balance validation.
    Issue #7: Validates and records transaction with reference_id and balance_after.
    """
    try:
        amount_paise = rupees_to_paise(amount_rupees)
    except ValueError:
        return None, "Invalid withdrawal amount format", 400

    if amount_paise <= 0:
        return None, "Enter a valid amount. Withdrawal amount must be greater than zero.", 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, account_number, user_id, balance, status FROM accounts WHERE id = ?",
        (account_id,),
    )
    acc = cursor.fetchone()
    if not acc:
        return None, "Account not found", 404

    can_access, err_code, err_msg = assert_can_access_account(user, acc)
    if not can_access:
        return None, err_msg, err_code

    if acc["status"] == AccountStatus.FROZEN.value:
        return None, "Account is frozen. Transactions are temporarily suspended.", 403
    if acc["status"] == AccountStatus.CLOSED.value:
        return None, "Cannot perform transactions on a closed account.", 400

    if acc["balance"] < amount_paise:
        return (
            None,
            f"Insufficient funds. Available balance: ₹{paise_to_rupees_str(acc['balance'])}, Requested: ₹{paise_to_rupees_str(amount_paise)}",
            400,
        )

    new_balance = acc["balance"] - amount_paise
    ref_id = generate_transaction_reference()
    desc = (description or "").strip() or "Cash/ATM Withdrawal"

    try:
        cursor.execute("BEGIN TRANSACTION")
        cursor.execute(
            "UPDATE accounts SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_balance, account_id),
        )
        cursor.execute(
            """
            INSERT INTO transactions (reference_id, account_id, transaction_type, amount, balance_after, description)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ref_id, account_id, TransactionType.WITHDRAWAL.value, amount_paise, new_balance, desc),
        )
        txn_id = cursor.lastrowid
        db.commit()
    except Exception as e:
        db.rollback()
        return None, f"Transaction failed: {str(e)}", 500

    log_event(
        "WITHDRAWAL_PROCESSED",
        user_id=user.id,
        details=f"Withdrew ₹{paise_to_rupees_str(amount_paise)} from account {acc['account_number']} (Ref: {ref_id})",
    )

    return {
        "transaction_id": txn_id,
        "reference_id": ref_id,
        "account_id": account_id,
        "account_number": acc["account_number"],
        "transaction_type": TransactionType.WITHDRAWAL.value,
        "amount": paise_to_rupees_str(amount_paise),
        "amount_paise": amount_paise,
        "balance_after": paise_to_rupees_str(new_balance),
        "balance_after_paise": new_balance,
        "description": desc,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, None, 201


def execute_transfer(
    user,
    source_account_id: int = None,
    destination_account_number: str = None,
    destination_account_id: int = None,
    amount_rupees: str = None,
    description: str = None,
    source_account_number: str = None,
    _simulate_failure_after_debit: bool = False,
):
    """
    Issue #8: Fund Transfer Between Accounts.
    Issue #9: Atomic Transfer & Rollback — ensures source debit, destination credit,
    and transaction/transfer ledger records complete atomically or roll back completely.
    """
    if amount_rupees is None or str(amount_rupees).strip() == "":
        return None, "Transfer amount is required", 400

    try:
        amount_paise = rupees_to_paise(amount_rupees)
    except ValueError:
        return None, "Invalid transfer amount format", 400

    if amount_paise <= 0:
        return None, "Enter a valid amount. Transfer amount must be greater than zero.", 400

    db = get_db()
    cursor = db.cursor()

    # 1. Resolve and validate source account
    if source_account_id is not None:
        try:
            source_account_id = int(source_account_id)
        except (ValueError, TypeError):
            return None, "Invalid source_account_id", 400
        cursor.execute(
            "SELECT id, account_number, user_id, balance, status FROM accounts WHERE id = ?",
            (source_account_id,),
        )
    elif source_account_number:
        cursor.execute(
            "SELECT id, account_number, user_id, balance, status FROM accounts WHERE account_number = ?",
            (str(source_account_number).strip(),),
        )
    else:
        return None, "Source account is required", 400

    source_acc = cursor.fetchone()
    if not source_acc:
        return None, "Source account not found", 404

    can_access, err_code, err_msg = assert_can_access_account(user, source_acc)
    if not can_access:
        return None, err_msg, err_code

    if source_acc["status"] == AccountStatus.FROZEN.value:
        return None, "Source account is frozen. Transactions are temporarily suspended.", 403
    if source_acc["status"] == AccountStatus.CLOSED.value:
        return None, "Cannot perform transactions on a closed account.", 400

    # 2. Resolve and validate destination account
    dest_acc = None
    if destination_account_number is not None and str(destination_account_number).strip() != "":
        dest_num_clean = str(destination_account_number).strip()
        cursor.execute(
            "SELECT id, account_number, user_id, balance, status FROM accounts WHERE account_number = ?",
            (dest_num_clean,),
        )
        dest_acc = cursor.fetchone()
    elif destination_account_id is not None and str(destination_account_id).strip() != "":
        try:
            dest_id_int = int(destination_account_id)
        except (ValueError, TypeError):
            return None, "Invalid destination_account_id", 400
        cursor.execute(
            "SELECT id, account_number, user_id, balance, status FROM accounts WHERE id = ?",
            (dest_id_int,),
        )
        dest_acc = cursor.fetchone()
    else:
        return None, "Destination account number or ID is required", 400

    if not dest_acc:
        return None, "Destination account not found", 404

    if source_acc["id"] == dest_acc["id"]:
        return None, "Cannot transfer funds to the same account.", 400

    if dest_acc["status"] == AccountStatus.FROZEN.value:
        return None, "Destination account is frozen. Cannot receive transfers.", 403
    if dest_acc["status"] == AccountStatus.CLOSED.value:
        return None, "Cannot transfer funds to a closed destination account.", 400

    # 3. Validate sufficient funds in source account
    if source_acc["balance"] < amount_paise:
        return (
            None,
            f"Insufficient funds. Available balance: ₹{paise_to_rupees_str(source_acc['balance'])}, Requested: ₹{paise_to_rupees_str(amount_paise)}",
            400,
        )

    new_source_balance = source_acc["balance"] - amount_paise
    new_dest_balance = dest_acc["balance"] + amount_paise
    transfer_ref = generate_transaction_reference()
    debit_ref = f"{transfer_ref}-DR"
    credit_ref = f"{transfer_ref}-CR"

    clean_desc = (description or "").strip()
    debit_desc = f"Transfer to A/C {dest_acc['account_number']}" + (f" - {clean_desc}" if clean_desc else "")
    credit_desc = f"Transfer from A/C {source_acc['account_number']}" + (f" - {clean_desc}" if clean_desc else "")
    transfer_desc = clean_desc or f"Transfer from {source_acc['account_number']} to {dest_acc['account_number']}"

    # 4. Atomic execution of debit, credit, and ledger entries (#9)
    try:
        cursor.execute("BEGIN TRANSACTION")

        # Step A: Debit source account
        cursor.execute(
            "UPDATE accounts SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_source_balance, source_acc["id"]),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("Failed to update source account balance")

        if _simulate_failure_after_debit:
            raise RuntimeError("Simulated mid-transfer failure after debiting source account")

        # Step B: Credit destination account
        cursor.execute(
            "UPDATE accounts SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_dest_balance, dest_acc["id"]),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("Failed to update destination account balance")

        # Step C: Insert debit transaction record for source account
        cursor.execute(
            """
            INSERT INTO transactions (reference_id, account_id, transaction_type, amount, balance_after, description)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                debit_ref,
                source_acc["id"],
                TransactionType.TRANSFER_OUT.value,
                amount_paise,
                new_source_balance,
                debit_desc,
            ),
        )
        debit_txn_id = cursor.lastrowid

        # Step D: Insert credit transaction record for destination account
        cursor.execute(
            """
            INSERT INTO transactions (reference_id, account_id, transaction_type, amount, balance_after, description)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                credit_ref,
                dest_acc["id"],
                TransactionType.TRANSFER_IN.value,
                amount_paise,
                new_dest_balance,
                credit_desc,
            ),
        )
        credit_txn_id = cursor.lastrowid

        # Step E: Insert transfer record into transfers table
        cursor.execute(
            """
            INSERT INTO transfers (
                reference_id, source_account_id, destination_account_id,
                amount, source_balance_after, destination_balance_after, description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transfer_ref,
                source_acc["id"],
                dest_acc["id"],
                amount_paise,
                new_source_balance,
                new_dest_balance,
                transfer_desc,
            ),
        )
        transfer_id = cursor.lastrowid

        db.commit()
    except Exception as e:
        db.rollback()
        try:
            log_event(
                "TRANSFER_ROLLED_BACK",
                user_id=user.id,
                details=f"Rolled back transfer of ₹{paise_to_rupees_str(amount_paise)} from {source_acc['account_number']} to {dest_acc['account_number']}: {str(e)}",
            )
        except Exception:
            pass
        return None, f"Transfer failed and was rolled back: {str(e)}", 500

    log_event(
        "TRANSFER_PROCESSED",
        user_id=user.id,
        details=f"Transferred ₹{paise_to_rupees_str(amount_paise)} from {source_acc['account_number']} to {dest_acc['account_number']} (Ref: {transfer_ref})",
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    transfer_payload = {
        "transfer_id": transfer_id,
        "debit_transaction_id": debit_txn_id,
        "credit_transaction_id": credit_txn_id,
        "reference_id": transfer_ref,
        "debit_reference_id": debit_ref,
        "credit_reference_id": credit_ref,
        "source_account_id": source_acc["id"],
        "source_account_number": source_acc["account_number"],
        "destination_account_id": dest_acc["id"],
        "destination_account_number": dest_acc["account_number"],
        "amount": paise_to_rupees_str(amount_paise),
        "amount_paise": amount_paise,
        "source_balance_after": paise_to_rupees_str(new_source_balance),
        "source_balance_after_paise": new_source_balance,
        "destination_balance_after": paise_to_rupees_str(new_dest_balance),
        "destination_balance_after_paise": new_dest_balance,
        "balance_after": paise_to_rupees_str(new_source_balance),
        "balance_after_paise": new_source_balance,
        "transaction_type": TransactionType.TRANSFER_OUT.value,
        "description": transfer_desc,
        "created_at": now_iso,
    }
    return transfer_payload, None, 201


def get_account_transactions(user, account_id: int):
    """
    Issue #7: Retrieve transaction history for an account.
    Ownership enforced: Customer can only view own transactions; Employee/Admin can view all.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, account_number, user_id FROM accounts WHERE id = ?",
        (account_id,),
    )
    acc = cursor.fetchone()
    if not acc:
        return None, "Account not found", 404

    can_access, err_code, err_msg = assert_can_access_account(user, acc)
    if not can_access:
        return None, err_msg, err_code

    cursor.execute(
        """
        SELECT id, reference_id, account_id, transaction_type, amount, balance_after, description, created_at
        FROM transactions
        WHERE account_id = ?
        ORDER BY id DESC
        """,
        (account_id,),
    )
    rows = cursor.fetchall()
    txns = [
        {
            "id": r["id"],
            "reference_id": r["reference_id"],
            "account_id": r["account_id"],
            "transaction_type": r["transaction_type"],
            "amount_paise": r["amount"],
            "amount": paise_to_rupees_str(r["amount"]),
            "balance_after_paise": r["balance_after"],
            "balance_after": paise_to_rupees_str(r["balance_after"]),
            "description": r["description"],
            "created_at": str(r["created_at"]),
        }
        for r in rows
    ]
    return txns, None, 200


def get_account_transfers(user, account_id: int):
    """
    Issue #8: Retrieve fund transfers involving an account (as source or destination).
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, account_number, user_id FROM accounts WHERE id = ?",
        (account_id,),
    )
    acc = cursor.fetchone()
    if not acc:
        return None, "Account not found", 404

    can_access, err_code, err_msg = assert_can_access_account(user, acc)
    if not can_access:
        return None, err_msg, err_code

    cursor.execute(
        """
        SELECT t.id, t.reference_id, t.source_account_id, s.account_number AS source_account_number,
               t.destination_account_id, d.account_number AS destination_account_number,
               t.amount, t.source_balance_after, t.destination_balance_after,
               t.description, t.created_at
        FROM transfers t
        JOIN accounts s ON t.source_account_id = s.id
        JOIN accounts d ON t.destination_account_id = d.id
        WHERE t.source_account_id = ? OR t.destination_account_id = ?
        ORDER BY t.id DESC
        """,
        (account_id, account_id),
    )
    rows = cursor.fetchall()
    transfers = [
        {
            "id": r["id"],
            "reference_id": r["reference_id"],
            "source_account_id": r["source_account_id"],
            "source_account_number": r["source_account_number"],
            "destination_account_id": r["destination_account_id"],
            "destination_account_number": r["destination_account_number"],
            "direction": "outgoing" if r["source_account_id"] == account_id else "incoming",
            "amount_paise": r["amount"],
            "amount": paise_to_rupees_str(r["amount"]),
            "source_balance_after_paise": r["source_balance_after"],
            "source_balance_after": paise_to_rupees_str(r["source_balance_after"]),
            "destination_balance_after_paise": r["destination_balance_after"],
            "destination_balance_after": paise_to_rupees_str(r["destination_balance_after"]),
            "description": r["description"],
            "created_at": str(r["created_at"]),
        }
        for r in rows
    ]
    return transfers, None, 200


# ==============================================================================
# 6. BLUEPRINT ROUTES
# ==============================================================================
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
user_bp = Blueprint("users", __name__, url_prefix="/api/users")
account_bp = Blueprint("accounts", __name__, url_prefix="/api/accounts")
transfer_bp = Blueprint("transfers", __name__, url_prefix="/api/transfers")


# --- Auth Endpoints (#2) ---
@auth_bp.route("/csrf", methods=["GET"])
def get_csrf():
    return jsonify({"csrf_token": generate_csrf_token()}), 200


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    user_dict, err, code = register_user(
        data.get("username"), data.get("email"), data.get("full_name"), data.get("password")
    )
    if err:
        return jsonify({"error": err}), code
    return jsonify({"message": "Registration successful", "user": user_dict}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    login_id = data.get("username") or data.get("email") or data.get("login_id")
    user_obj, err, code = authenticate_user(login_id, data.get("password"))
    if err:
        return jsonify({"error": err}), code

    login_user(user_obj, remember=False)
    session.permanent = True
    token = generate_csrf_token()
    return jsonify({"message": "Login successful", "user": user_obj.to_dict(), "csrf_token": token}), 200


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    uid = current_user.id if current_user.is_authenticated else None
    uname = current_user.username if current_user.is_authenticated else "unknown"
    logout_user()
    session.clear()
    log_event("LOGOUT", user_id=uid, details=f"User {uname} logged out")
    return jsonify({"message": "Logged out successfully"}), 200


@auth_bp.route("/me", methods=["GET"])
def get_me():
    if not current_user.is_authenticated:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify({"user": current_user.to_dict(), "csrf_token": generate_csrf_token()}), 200


# --- User & RBAC Endpoints (#3) ---
@user_bp.route("", methods=["GET"])
@role_required(Role.ADMIN.value)
def list_users():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, username, email, full_name, role, is_active, created_at FROM users ORDER BY id ASC")
    rows = cursor.fetchall()
    return jsonify({
        "users": [
            {
                "id": r["id"],
                "username": r["username"],
                "email": r["email"],
                "full_name": r["full_name"],
                "role": r["role"],
                "is_active": bool(r["is_active"]),
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ]
    }), 200


@user_bp.route("/<int:user_id>/role", methods=["PATCH"])
@role_required(Role.ADMIN.value)
def change_user_role(user_id):
    if current_user.id == user_id:
        return jsonify({"error": "Administrators cannot change or demote their own role"}), 400

    data = request.get_json(silent=True) or {}
    new_role = data.get("role")
    if new_role not in Role.all_roles():
        return jsonify({"error": f"Invalid role. Allowed: {', '.join(Role.all_roles())}"}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,))
    target = cursor.fetchone()
    if not target:
        return jsonify({"error": "User not found"}), 404

    cursor.execute("UPDATE users SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_role, user_id))
    db.commit()
    log_event("USER_ROLE_CHANGED", user_id=current_user.id, details=f"Changed user {target['username']} role to {new_role}")
    return jsonify({"message": "User role updated successfully", "user": {"id": user_id, "role": new_role}}), 200


@user_bp.route("/<int:user_id>/status", methods=["PATCH"])
@role_required(Role.ADMIN.value)
def change_user_status(user_id):
    if current_user.id == user_id:
        return jsonify({"error": "Administrators cannot deactivate their own account"}), 400

    data = request.get_json(silent=True) or {}
    if "is_active" not in data:
        return jsonify({"error": "'is_active' boolean required"}), 400

    is_active = bool(data["is_active"])
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
    target = cursor.fetchone()
    if not target:
        return jsonify({"error": "User not found"}), 404

    cursor.execute("UPDATE users SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (1 if is_active else 0, user_id))
    db.commit()
    log_event("USER_STATUS_CHANGED", user_id=current_user.id, details=f"Set user {target['username']} active={is_active}")
    return jsonify({"message": "User status updated successfully", "user": {"id": user_id, "is_active": is_active}}), 200


# --- Account & Financial Transactions Endpoints (#4, #5, #6, #7, #8, #9) ---
@account_bp.route("", methods=["POST"])
@login_required
def open_account():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if current_user.role == Role.CUSTOMER.value:
        user_id = current_user.id
    elif not user_id:
        return jsonify({"error": "user_id is required for employee/admin to open an account"}), 400

    account, err, code = create_account(
        creator_user=current_user,
        user_id=int(user_id),
        account_type=data.get("account_type", "savings"),
        initial_deposit_rupees=data.get("initial_deposit", "0.00"),
    )
    if err:
        return jsonify({"error": err}), code
    return jsonify({"message": "Account created successfully", "account": account}), 201


@account_bp.route("", methods=["GET"])
@login_required
def list_accs():
    search = request.args.get("search", None)
    accounts = get_accounts(current_user, search_query=search)
    return jsonify({"accounts": accounts}), 200


@account_bp.route("/<int:account_id>", methods=["GET"])
@login_required
def get_acc_detail(account_id):
    account, err, code = get_account_by_id(current_user, account_id)
    if err:
        return jsonify({"error": err}), code
    return jsonify({"account": account}), 200


@account_bp.route("/<int:account_id>/balance", methods=["GET"])
@login_required
def get_acc_balance(account_id):
    account, err, code = get_account_by_id(current_user, account_id)
    if err:
        return jsonify({"error": err}), code
    return jsonify({
        "account_id": account["id"],
        "account_number": account["account_number"],
        "balance_paise": account["balance_paise"],
        "balance": account["balance"],
        "status": account["status"],
    }), 200


@account_bp.route("/<int:account_id>/status", methods=["PATCH"])
@role_required(Role.ADMIN.value, Role.EMPLOYEE.value)
def patch_acc_status(account_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if not new_status:
        return jsonify({"error": "'status' is required"}), 400
    res, err, code = update_account_status(current_user, account_id, new_status)
    if err:
        return jsonify({"error": err}), code
    return jsonify({"message": "Account status updated successfully", "account": res}), 200


@account_bp.route("/<int:account_id>/deposit", methods=["POST"])
@login_required
def deposit_to_account(account_id):
    """Issue #5: Deposit money; Issue #7: Records transaction."""
    data = request.get_json(silent=True) or {}
    amount = data.get("amount")
    description = data.get("description")

    txn, err, code = execute_deposit(current_user, account_id, amount, description)
    if err:
        return jsonify({"error": err}), code
    return jsonify({"message": "Deposit successful", "transaction": txn}), 201


@account_bp.route("/<int:account_id>/withdraw", methods=["POST"])
@login_required
def withdraw_from_account(account_id):
    """Issue #6: Withdraw money; Issue #7: Validates balance and records transaction."""
    data = request.get_json(silent=True) or {}
    amount = data.get("amount")
    description = data.get("description")

    txn, err, code = execute_withdrawal(current_user, account_id, amount, description)
    if err:
        return jsonify({"error": err}), code
    return jsonify({"message": "Withdrawal successful", "transaction": txn}), 201


@account_bp.route("/<int:account_id>/transfer", methods=["POST"])
@login_required
def transfer_from_account(account_id):
    """Issue #8 & #9: Atomic fund transfer from source account_id to destination account."""
    data = request.get_json(silent=True) or {}
    dest_acc_num = (
        data.get("destination_account_number")
        or data.get("to_account_number")
        or data.get("target_account_number")
        or data.get("destination_account")
    )
    dest_acc_id = (
        data.get("destination_account_id")
        or data.get("to_account_id")
        or data.get("target_account_id")
    )
    amount = data.get("amount")
    description = data.get("description")

    transfer_res, err, code = execute_transfer(
        user=current_user,
        source_account_id=account_id,
        destination_account_number=dest_acc_num,
        destination_account_id=dest_acc_id,
        amount_rupees=amount,
        description=description,
    )
    if err:
        return jsonify({"error": err}), code
    return jsonify({"message": "Transfer successful", "transfer": transfer_res, "transaction": transfer_res}), 201


@account_bp.route("/transfer", methods=["POST"])
@transfer_bp.route("", methods=["POST"])
@login_required
def initiate_transfer():
    """Issue #8 & #9: Top-level atomic fund transfer endpoint."""
    data = request.get_json(silent=True) or {}
    src_acc_id = data.get("source_account_id") or data.get("from_account_id")
    src_acc_num = (
        data.get("source_account_number")
        or data.get("from_account_number")
        or data.get("source_account")
    )
    dest_acc_num = (
        data.get("destination_account_number")
        or data.get("to_account_number")
        or data.get("target_account_number")
        or data.get("destination_account")
    )
    dest_acc_id = (
        data.get("destination_account_id")
        or data.get("to_account_id")
        or data.get("target_account_id")
    )
    amount = data.get("amount")
    description = data.get("description")

    transfer_res, err, code = execute_transfer(
        user=current_user,
        source_account_id=src_acc_id,
        source_account_number=src_acc_num,
        destination_account_number=dest_acc_num,
        destination_account_id=dest_acc_id,
        amount_rupees=amount,
        description=description,
    )
    if err:
        return jsonify({"error": err}), code
    return jsonify({"message": "Transfer successful", "transfer": transfer_res, "transaction": transfer_res}), 201


@account_bp.route("/<int:account_id>/transfers", methods=["GET"])
@login_required
def list_account_transfers(account_id):
    """Issue #8: Get transfer records involving an account."""
    transfers, err, code = get_account_transfers(current_user, account_id)
    if err:
        return jsonify({"error": err}), code
    return jsonify({"transfers": transfers}), 200


@account_bp.route("/<int:account_id>/transactions", methods=["GET"])
@login_required
def list_account_txns(account_id):
    """Issue #7: Get transaction history for an account."""
    txns, err, code = get_account_transactions(current_user, account_id)
    if err:
        return jsonify({"error": err}), code
    return jsonify({"transactions": txns}), 200


# ==============================================================================
# 7. APP FACTORY
# ==============================================================================
def create_app(custom_config=None):
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-pes-bank-mini-project")
    app.config["DATABASE_PATH"] = os.environ.get("DATABASE_PATH", "bank.db")
    app.config["SESSION_COOKIE_HTTPONLY"] = os.environ.get("SESSION_COOKIE_HTTPONLY", "True").lower() == "true"
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "False").lower() == "true"
    app.config["SESSION_COOKIE_SAMESITE"] = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
    lifetime_min = int(os.environ.get("PERMANENT_SESSION_LIFETIME_MINUTES", "30"))
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=lifetime_min)
    cors_str = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    app.config["CORS_ORIGINS"] = [x.strip() for x in cors_str.split(",") if x.strip()]

    if custom_config:
        app.config.update(custom_config)

    app.teardown_appcontext(close_db)

    CORS(app, origins=app.config["CORS_ORIGINS"], supports_credentials=True)

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return get_user_by_id(int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({"error": "Authentication required"}), 401

    @app.before_request
    def start_timer():
        g.start_time = time.time()

    @app.before_request
    def check_csrf():
        return verify_csrf_token()

    @app.after_request
    def apply_security_headers_and_timing(response):
        # Issue #19: Security Headers & Role Data Protection
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'

        # Issue #20: System Response Time tracking (Server-Timing & X-Response-Time in ms)
        if hasattr(g, 'start_time'):
            elapsed_ms = (time.time() - g.start_time) * 1000
            response.headers['Server-Timing'] = f'total;dur={elapsed_ms:.2f}'
            response.headers['X-Response-Time'] = f'{elapsed_ms:.2f}ms'
        return response

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "healthy", "service": "Bank Management System API"}), 200

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(transfer_bp)

    @app.errorhandler(400)
    def err_bad_req(e):
        return jsonify({"error": "Bad request"}), 400

    @app.errorhandler(401)
    def err_unauth(e):
        return jsonify({"error": "Authentication required"}), 401

    @app.errorhandler(403)
    def err_forbidden(e):
        return jsonify({"error": "Access forbidden: insufficient permissions"}), 403

    @app.errorhandler(404)
    def err_not_found(e):
        return jsonify({"error": "Requested resource not found"}), 404

    @app.errorhandler(500)
    def err_server(e):
        return jsonify({"error": "Internal server error"}), 500

    return app
