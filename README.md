# DealerOS — Dual-Ledger Reconciliation Web Application

A full-stack financial reconciliation platform built to compare two asynchronous accounting systems (**System A** and **System B**) to identify ledger discrepancies without ever leaking confidential data across tenant organizational boundaries.

---

## 1. How to Run (From a Clean Clone)

Follow these exact steps in order.

### Prerequisites
- **Python 3.11+** (verified on Python 3.14)
- **Node.js 18+** (verified on Node v24)
- **Git**

### Step 1: Clone and Set Up Virtual Environment
```bash
git clone <repo-url> dealeros
cd dealeros

# Create and activate Python virtual environment
python -m venv .venv
# On Windows (cmd/powershell):
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt
```

### Step 2: Database Setup & Data Import
```bash
cd backend

# Run database migrations (creates SQLite tables)
python manage.py migrate

# Run the idempotent data importer
python manage.py import_data

# Run tests to verify setup
pytest
```
*Expected importer output:*
```
Locations: 5 saved; A: 120 read, 120 saved; B: 121 read, 121 saved; values left empty: 1; refs cleaned: 3
```

### Step 3: Run the Backend Server
```bash
# In the backend/ folder:
python manage.py runserver 127.0.0.1:8000
```
Backend API will be running at `http://127.0.0.1:8000/api/disagreements/?org=ORG-A`.

### Step 4: Run the Frontend Application
Open a second terminal window:
```bash
cd dealeros/frontend
npm install
npm run dev
```
Open your browser at `http://localhost:5173`.

---

## 2. What Was Built

- **Database Models (`backend/reconcile/models.py`)**:
  - `Location`: Authoritative mapping between physical branches (`location_id`) and customer organizations (`org_id`).
  - `SystemARecord`: 120 ledger events stored with high-precision `DecimalField`. Empty actor IDs stored as null.
  - `SystemBEntry`: 121 ledger entries with both cleaned and raw reference text (`record_ref_raw`, `value_raw`) for full auditability. No foreign key to System A, safely supporting orphan entries.
- **Idempotent Importer (`backend/reconcile/importer.py`)**:
  - Safe parsing of dirty references (`rec1034`, ` REC - 1070 `, `1112`).
  - Safe parsing of non-standard currency formats (e.g., Indian comma `1,25,400.00`).
  - Re-runnable without row duplication (`update_or_create`).
- **Pure Python Reconciliation Engine (`backend/reconcile/compare.py`)**:
  - Catches `MISSING_IN_B`, `ORPHAN_IN_B`, `DUPLICATE_IN_B`, `VALUE_MISMATCH`, `LOCATION_MISMATCH`, `DATE_MISMATCH`, and `VOIDED_RECORD_HAS_ENTRY`.
  - Accurately distinguishes between duplicate entries and valid split entries (`part 1 of 2` summing to total).
- **Tenant-Isolated API (`backend/reconcile/views.py`)**:
  - `GET /api/disagreements/?org=ORG-A&reason=...&sort=...`
  - Strict SQL filtering by `location__org_id` prevents tenant leakage in API payloads.
  - Masking of foreign location codes for cross-tenant trap rows (`[EXTERNAL_LOCATION]`).
- **Responsive Web Dashboard (`frontend/`)**:
  - Vite + React single-page application.
  - Interactive tenant organization switcher (`ORG-A` / `ORG-B`).
  - Live discrepancy reason filter and metric summary pills.
  - Sortable table columns (Value, Difference, Record ID, Reason).
  - Empty cells displayed cleanly (`—`), never defaulting missing values to `0` or `null`.

---

## 3. What Was Deliberately Not Built

To prioritize core correctness, data integrity, and strict tenant safety, the following secondary features were intentionally omitted:
- **Authentication & User Management**: Replaced with an explicit, secure tenant selector query parameter (`?org=ORG-A`).
- **Pagination**: The dataset is small (~120 rows); rendering in a single responsive table offers immediate end-to-end auditability.
- **Docker / Containerization**: Standard virtual environment and npm commands keep setup lightweight and frictionless.
- **Excessive CSS Frameworks**: Built using clean, custom responsive CSS without bloated third-party UI libraries.

---

## 4. How I Worked with the AI Agent

- **Tool Used**: Google Antigravity Agent.
- **Division of Work**:
  - Used the agent to analyze raw CSV anomalies and generate preliminary project boilerplate.
  - Guided the agent with targeted requirements on idempotent database updates, Decimal arithmetic, and pure Python reconciliation rules.
  - Hand-verified all test cases, comparing raw CSV entries (e.g. REC-1042 duplicate vs REC-1055 split) directly against business logic requirements.
  - Wrote and enforced the tenant isolation unit tests and cross-tenant location masking rules.

---

## 5. Review Call Questions

### a. One thing the AI agent got wrong. How did you notice?
When handling the cross-tenant trap row (`REC-1077`), the AI agent initially assumed that because entry `ENT/2026/4077` had location `LOC-201` (which belongs to `ORG-B`), it should be returned as an `ORPHAN_IN_B` when `ORG-B` called the API. I noticed this when our automated tenant isolation test (`test_tenant.py`) failed: `REC-1077` was visible to `ORG-B`! In reality, `REC-1077` is NOT an orphan—it is an existing System A record belonging to `ORG-A` (`LOC-102`) that was misallocated in System B. We corrected this by tracking global System A record IDs to distinguish true orphans (like `REC-1999`) from cross-tenant misallocations, ensuring `ORG-B` has zero visibility into `ORG-A` records.

### b. The part you are least confident about, and why
The handling of cross-system date differences (`DATE_MISMATCH`). In our implementation, `REC-1009` is flagged because System A recorded the event on `2026-03-31` while System B recorded it on `2026-04-02`. In real-world enterprise integrations, transactions occurring over weekends, holidays, or across timezones routinely settle 1–2 business days later without representing an operational error. In a live production deployment, I would consult with the finance department to define an acceptable threshold (e.g., T+2 settlement window) rather than flagging every minor date divergence as an error.

### c. If you had a second day, what would you fix first?
I would add a ledger resolution and audit workflow directly into the platform (e.g. `POST /api/disagreements/{id}/resolve` with resolution reasons such as `APPROVED_SPLIT`, `SETTLEMENT_TIMING`, or `MANUAL_OVERRIDE`). Currently, operations teams can identify discrepancies, but cannot record whether a discrepancy has been acknowledged, dismissed, or forwarded to accounting.
