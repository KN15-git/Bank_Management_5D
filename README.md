# PES University Bank Management System

Academic Software Engineering Mini-Project — Bank Management System implementation for Issues #2, #3, #4, #5, #6, #7, #8, and #9.

---

## 1. Scope & Implemented Issues
- **Issue #2**: Authentication & Login (Server-side signed HttpOnly sessions via Flask-Login, bcrypt password hashing, brute-force lockout, CSRF protection).
- **Issue #3**: Role-Based Access Control (Roles: `customer`, `employee`, `admin`, server-side `@role_required` enforcement, ownership isolation, user lifecycle management).
- **Issue #4**: Account & Balance Management (12-digit collision-safe account numbers, integer paise storage, currency formatting, status lifecycle active/frozen/closed with zero-balance closure invariant).
- **Issue #5**: Deposit Money (Validate deposit amount > 0, immediate account balance update, frozen/closed status rejection).
- **Issue #6**: Withdraw Money (Validate withdrawal amount > 0, strict balance check ensuring no overdraft, immediate balance update, frozen/closed status rejection).
- **Issue #7**: Transaction Validation & Recording (Atomic transaction processing, unique reference ID generation, persistent transaction ledger storing amount, type, resulting balance, and timestamp).
- **Issue #8**: Fund Transfer Between Accounts (Transfer funds from a source account to a destination account by 12-digit account number or ID, validating source ownership, active account statuses, non-self transfer, and sufficient balance, while recording `transfer_out` and `transfer_in` ledger entries plus transfer records).
- **Issue #9**: Atomic Transfer & Rollback (All-or-nothing execution across source debit, destination credit, transaction ledger entries, and transfer record; automatic `ROLLBACK` on any failure so accounts and ledgers never enter an inconsistent state).

---

## 2. Tech Stack
- **Backend**: Python 3.10+, Flask REST API, Flask-Login, Flask-CORS, bcrypt, SQLite (`PRAGMA foreign_keys = ON;`)
- **Frontend**: React 18, React Router v6, Plain CSS, Vite dev server with proxy
- **Testing**: pytest (32 test cases passing), Postman Collection

---

## 3. Quick Setup & Execution

### Backend Setup
```bash
cd backend
python -m venv venv
# On Windows (Command Prompt):
venv\Scripts\activate
# On Windows (PowerShell):
# .\venv\Scripts\Activate.ps1
# On Linux/macOS:
# source venv/bin/activate

pip install -r requirements.txt
copy .env.example .env

# Run database seed
python seed.py

# Launch REST API server (Runs on http://127.0.0.1:5000)
python run.py
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
# Frontend is served at http://localhost:5173
```

### Automated Tests
```bash
cd backend
pytest -v
```

---

## 4. Default Seeded Credentials
| Role | Username | Password | Email |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin_boss` | `AdminPassword@123` | `admin@pesbank.com` |
| **Employee** | `teller_priya` | `TellerPass@123` | `priya.teller@pesbank.com` |
| **Customer** | `rahul_k` | `Bank@1234` | `rahul.k@example.com` |
| **Customer** | `anita_s` | `AnitaSecure@123` | `anita.s@example.com` |
| **Customer** | `vikram_m` | `Vikram@Pass123` | `vikram.m@example.com` |

---

## 5. Security & Financial Invariants
- **No Float Arithmetic**: All account balances and transaction amounts are stored strictly as integer `paise` in SQLite (`CHECK(balance >= 0)`, `CHECK(amount > 0)`). Decimal formatting to rupees occurs only at the presentation and API boundaries.
- **CSRF Token Pattern**: State-changing requests (`POST`, `PATCH`) validate the `X-CSRF-Token` header matching the session token.
- **Brute Force Lockout**: 5 failed login attempts trigger an automatic 15-minute lockout.
- **Transaction & Transfer Atomicity**: Deposits, withdrawals, and inter-account transfers execute within database transactions (`BEGIN TRANSACTION` ... `COMMIT` / `ROLLBACK`), updating account balances and inserting ledger records atomically.
- **Audit Logging**: Security and account lifecycle events (`LOGIN_SUCCESS`, `ACCOUNT_CREATED`, `ACCOUNT_STATUS_CHANGED`, `DEPOSIT_PROCESSED`, `WITHDRAWAL_PROCESSED`, `TRANSFER_PROCESSED`, `TRANSFER_ROLLED_BACK`) are recorded into `audit_logs`.
