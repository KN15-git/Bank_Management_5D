"""Seed database with Admin, Employee, and Customers + sample accounts."""
from app import create_app, get_db, init_db, Role, AccountStatus, AccountType, hash_password

SAMPLE_USERS = [
    {
        "username": "admin_boss",
        "email": "admin@pesbank.com",
        "full_name": "System Administrator",
        "password": "AdminPassword@123",
        "role": Role.ADMIN.value,
    },
    {
        "username": "teller_priya",
        "email": "priya.teller@pesbank.com",
        "full_name": "Priya Sharma (Officer)",
        "password": "TellerPass@123",
        "role": Role.EMPLOYEE.value,
    },
    {
        "username": "rahul_k",
        "email": "rahul.k@example.com",
        "full_name": "Rahul Kumar",
        "password": "Bank@1234",
        "role": Role.CUSTOMER.value,
    },
    {
        "username": "anita_s",
        "email": "anita.s@example.com",
        "full_name": "Anita Suresh",
        "password": "AnitaSecure@123",
        "role": Role.CUSTOMER.value,
    },
    {
        "username": "vikram_m",
        "email": "vikram.m@example.com",
        "full_name": "Vikram Mehta",
        "password": "Vikram@Pass123",
        "role": Role.CUSTOMER.value,
    },
]

SAMPLE_ACCOUNTS = [
    {
        "account_number": "100123456789",
        "username": "rahul_k",
        "account_type": AccountType.SAVINGS.value,
        "balance_paise": 2500000,  # ₹25,000.00
        "status": AccountStatus.ACTIVE.value,
    },
    {
        "account_number": "100123456790",
        "username": "rahul_k",
        "account_type": AccountType.CURRENT.value,
        "balance_paise": 10000000,  # ₹1,00,000.00
        "status": AccountStatus.ACTIVE.value,
    },
    {
        "account_number": "200987654321",
        "username": "anita_s",
        "account_type": AccountType.SAVINGS.value,
        "balance_paise": 5432000,  # ₹54,320.00
        "status": AccountStatus.ACTIVE.value,
    },
    {
        "account_number": "300456789123",
        "username": "vikram_m",
        "account_type": AccountType.SAVINGS.value,
        "balance_paise": 0,  # ₹0.00
        "status": AccountStatus.ACTIVE.value,
    },
]


def seed():
    app = create_app()
    with app.app_context():
        init_db()
        db = get_db()
        cursor = db.cursor()

        print("=" * 75)
        print("         PES BANK MANAGEMENT SYSTEM - SEEDED USER ACCOUNTS         ")
        print("=" * 75)

        user_map = {}
        for u in SAMPLE_USERS:
            cursor.execute("SELECT id FROM users WHERE username = ?", (u["username"],))
            row = cursor.fetchone()
            if row:
                user_map[u["username"]] = row["id"]
                continue
            cursor.execute(
                """
                INSERT INTO users (username, email, full_name, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (u["username"], u["email"], u["full_name"], hash_password(u["password"]), u["role"]),
            )
            user_map[u["username"]] = cursor.lastrowid
        db.commit()

        for a in SAMPLE_ACCOUNTS:
            cursor.execute("SELECT id FROM accounts WHERE account_number = ?", (a["account_number"],))
            if cursor.fetchone():
                continue
            owner_id = user_map.get(a["username"])
            if owner_id:
                cursor.execute(
                    """
                    INSERT INTO accounts (account_number, user_id, account_type, balance, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (a["account_number"], owner_id, a["account_type"], a["balance_paise"], a["status"]),
                )
        db.commit()

        print(f"{'Role':<10} | {'Username':<14} | {'Password':<18} | {'Email'}")
        print("-" * 75)
        for u in SAMPLE_USERS:
            print(f"{u['role']:<10} | {u['username']:<14} | {u['password']:<18} | {u['email']}")
        print("-" * 75)
        print("Sample Accounts:")
        for a in SAMPLE_ACCOUNTS:
            print(f"  Account: {a['account_number']} | Owner: {a['username']:<8} | Type: {a['account_type']:<7} | Balance: Rs. {a['balance_paise']/100:,.2f}")
        print("=" * 75)


if __name__ == "__main__":
    seed()
