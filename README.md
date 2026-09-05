# Bank_Management_5D

A role-based digital banking platform covering authentication, deposits/withdrawals, fund transfers, loan applications, and transaction history — with built-in security (RBAC) and performance monitoring.

> 📁 Repo: (https://github.com/KN15-git/Bank_Management_5D)

## Table of Contents

- [Overview](#overview)
- [Actors / Roles](#actors--roles)
- [Features (Functional Requirements)](#features-functional-requirements)
- [Non-Functional Requirements](#non-functional-requirements)
- [System Design (Use Case Model)](#system-design-use-case-model)
- [Use Case Scenarios](#use-case-scenarios)
- [Testing](#testing)
  - [Test Coverage Summary](#test-coverage-summary)
  - [Known Issues Found in Testing](#known-issues-found-in-testing)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## Overview

The Bank Management System Portal lets customers manage their money and lets bank staff manage the operations behind it, all through one system that enforces role-based access control (RBAC) at every entry point. The design is captured across four documents in this repo:

| Document | Purpose |
|---|---|
| `SRS_document.pdf` | Software Requirements Specification — functional & non-functional requirements |
| `Bank_UseCase_Flow.pdf` | Detailed use case scenarios (main + alternate flows) |
| `UML_diagram.pdf` | UML use case diagram for the whole portal |
| `Bank_Test_Plan.pdf` | Unit, integration, and system test cases per requirement |

## Actors / Roles

| Role | Description |
|---|---|
| **Customer** | Logs in, views balance, deposits/withdraws, transfers money, applies for loans, views transaction history |
| **Bank Employee** | Assists with deposits/withdrawals, views transaction logs |
| **Loan Officer** | Reviews, approves, or rejects loan applications |
| **Bank Manager** | Oversight across accounts and loan decisions |
| **System Admin** | Administers user accounts, configures system roles |
| **Auditor** | Views transaction logs and generates audit reports (with authorization) |

## Features (Functional Requirements)

| ID | Requirement | Priority | Pass Criteria |
|---|---|---|---|
| **FR-001** | Secure login with real-time view of account details and balance | High | Account details and balance load within 2 seconds of login |
| **FR-002** | Deposit/withdraw funds with immediate balance update | High | Balance reflects the transaction instantly with a confirmation shown |
| **FR-003** | Transfer money to another account within the bank | High | Transfer completes and both sender and receiver balances update correctly |
| **FR-004** | Apply for a loan online; loan officers review, approve, or reject | Medium | Application is submitted with a reference ID and appears in the officer's queue |
| **FR-005** | View transaction history (deposits, withdrawals, transfers) | Medium | All transactions from the last 12 months are listed with correct amounts and dates |

## Non-Functional Requirements

| ID | Type | Requirement | Priority | Pass Criteria |
|---|---|---|---|---|
| **NFR-001** | Security | Sensitive data encrypted at rest and in transit; access controlled by role (RBAC) | High | Data is encrypted; roles only see permitted data |
| **NFR-002** | Performance | Common actions (login, balance checks) respond within 2–3 seconds under normal load | Medium | 95% of requests complete within 3 seconds under expected load |

## System Design (Use Case Model)

The UML use case diagram models six actors interacting with the **Bank Management System Portal**, and two key relationships that thread through every use case:

- **Authenticate User** «includes» **Enforce RBAC (NFR-001)** — every login resolves the user's role before any further action is allowed.
- **Deposit/Withdraw Funds** is extended by **Performance Metric Check (NFR-002)**, which tracks response time against the 2–3 second target on every transaction.

Core use cases: Authenticate User, View Account Details, Deposit Funds, Withdraw Funds, Apply for Loan, Review & Accept/Reject Loan Applications, Administer User Accounts, Configure System Roles, View Transaction Logs, Generate Audit Reports, and Enforce Security Constraints (RBAC).

See `UML_diagram.pdf` for the full diagram.

## Use Case Scenarios

Full main-success and alternate flows are documented in `Bank_UseCase_Flow.pdf`. Summary:

### 1. Authenticate User
- **Actors:** Customer, Bank Employee, Loan Officer, Bank Manager, System Admin, Auditor
- **Flow:** User enters credentials → system validates → resolves role/permissions → creates session → redirects to dashboard.
- **Alternate flow:** Invalid credentials show a generic error (doesn't reveal which field was wrong); after 5 failed attempts the account is temporarily locked.
- **UML relationship:** «includes» Enforce RBAC (NFR-001).

### 2. Deposit / Withdraw Funds
- **Actors:** Customer, Bank Employee
- **Flow:** User selects deposit/withdrawal and enters amount → system validates against account rules → updates balance and records the transaction → shows confirmation.
- **Alternate flow:** Insufficient funds → withdrawal rejected, current balance shown.
- **UML relationship:** base use case for «extends» Monitor Performance (NFR-002).

### 3. Transfer Money
- **Actor:** Customer
- **Flow:** Customer enters receiver account + amount → system verifies receiver exists and sender has sufficient funds → debits sender and credits receiver atomically → confirmation shown.
- **Alternate flow:** Failure mid-transfer (e.g., after debit, before credit) triggers automatic rollback, an error, and a logged failed attempt for review.
- **UML relationship:** «includes» Authenticate User.

### 4. Apply for Loan
- **Actors:** Customer (applies), Loan Officer (reviews)
- **Flow:** Customer submits loan form → system validates and generates a reference ID → application enters officer's review queue → officer approves/rejects → customer is notified.
- **Alternate flow:** Missing required fields block submission with the fields highlighted.
- **UML relationship:** «includes» Authenticate User; Review Loan Applications is a separate, subsequently-triggered use case.

## Testing

Test coverage spans Unit (UT), Integration (IT), and System (ST) levels across all five functional requirements. Full test cases, pre-conditions, test data, and results are in `Bank_Test_Plan.pdf`.

### Test Coverage Summary

| Module | FR | UT Cases | IT Cases | ST Cases |
|---|---|---|---|---|
| Login & Authentication | FR-001 | 4 | 2 | 2 |
| Deposit & Withdrawal | FR-002 | 4 | 2 | 2 |
| Fund Transfer | FR-003 | 4 | 2 | 2 |
| Loan Management | FR-004 | 3 | 3 | 2 |
| Transaction History | FR-005 | 3 | 2 | 2 |

**Total: 33 test cases** (18 UT / 11 IT / 4 ST)

### Known Issues Found in Testing

These are open defects surfaced during the latest test run and should be tracked before release:

| Test Case | Module | Issue |
|---|---|---|
| IT_01 | Login & Authentication | Dashboard balance was off by ₹1 due to a caching delay |
| ST_01 | Login & Authentication | Under concurrent load, 47/50 logins completed within 2s; 3 took up to 2.4s |
| IT_03 | Deposit & Withdrawal | Deposit notification arrived after 4 minutes (target: 1 minute) due to a queue backlog |
| UT_12 | Fund Transfer | System allowed a transfer to the sender's own account with no warning shown (should be blocked) |
| IT_09 | Loan Management | Rejection notification sent, but the rejection reason field was blank |
| ST_10 | Transaction History | Statement export worked, but date formatting was inconsistent |

**Passing but worth monitoring:**
- IT_06 (Fund Transfer rollback) — rollback succeeded but took ~12 seconds.
- ST_04 (concurrent transaction load) — 96% of requests completed within 3 seconds (target: 95%), passing but close to threshold.

## Repository Structure

This is the current structure of [Bank_Management_5D](https://github.com/KN15-git/Bank_Management_5D):

```
Bank_Management_5D/
├── README.md
└── Documents/
    ├── SRS_document.pdf        # Functional & non-functional requirements
    ├── Bank_UseCase_Flow.pdf   # Detailed use case scenarios
    ├── UML_diagram.pdf         # UML use case diagram
    └── Bank_Test_Plan.pdf      # Test cases and results (UT/IT/ST)
```

The repo is currently **documentation-only** — it holds the design and QA artifacts for the Bank Management System, with no application source code committed yet.

## Getting Started

To move from documentation to implementation:

1. Clone the repo:
   ```bash
   git clone https://github.com/KN15-git/Bank_Management_5D.git
   cd Bank_Management_5D
   ```
2. Review `Documents/SRS_document.pdf` for the full requirements baseline.
3. Use `Documents/UML_diagram.pdf` and `Documents/Bank_UseCase_Flow.pdf` to scaffold the application's modules: Authentication/RBAC, Accounts, Transactions (Deposit/Withdraw/Transfer), Loans, and Audit/Reporting.
4. Use `Documents/Bank_Test_Plan.pdf` as the basis for the automated test suite, and resolve the [known issues](#known-issues-found-in-testing) above before release.
5. As implementation code is added, expand this structure — e.g. `src/`, `tests/`, `docs/` — and update this README's structure section accordingly.

## Roadmap

- [ ] Set up project scaffolding (backend, frontend/mobile client, database schema)
- [ ] Implement Authentication & RBAC (FR-001, NFR-001)
- [ ] Implement Deposit/Withdraw (FR-002)
- [ ] Implement Fund Transfer (FR-003)
- [ ] Implement Loan Application workflow (FR-004)
- [ ] Implement Transaction History (FR-005)
- [ ] Automate the test suite from `Bank_Test_Plan.pdf`
- [ ] Resolve known issues listed above
- [ ] Add CI/CD pipeline

## Contributing

1. Fork the repository and create a feature branch.
2. Reference the relevant FR/NFR/use case ID in your commit messages and pull request description.
3. Add or update test cases in the test plan for any new or changed functionality.
4. Open a pull request describing the change and its test coverage.

## License

No license has been specified yet for this repository. Add a `LICENSE` file to clarify usage rights.
