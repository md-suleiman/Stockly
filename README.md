# 📦 Stockly — Inventory & Resource Management System

> **Smarter Stock. Simpler Management.**

**Product Name:** Stockly  
**Dashboard Heading:** Resource Management  
**Academic Project Title:** Design and Development of Stockly – A Web-Based Inventory and Resource Management System  
**Domain:** Inventory & Resource Management  
**Target Users:** Small retail business owners, shop managers, and warehouse inventory personnel  
**Currency Standard:** Indian Rupees (₹)

---

## 📋 Overview

**Stockly** is a local-first, browser-based inventory management workspace for
retail business owners and inventory teams. Built with Python, Flask, SQLite,
Neon PostgreSQL, and vanilla frontend technologies (HTML5, CSS3, JavaScript),
it uses SQLite by default for local work and PostgreSQL when `DATABASE_URL` is
configured for production.

Stockly directly demonstrates core software engineering and programming paradigms:
- **Object-Oriented Programming (OOP):** Rich domain entities (`Product`, `StockTransaction`), encapsulation of SQLite/PostgreSQL connections via `Database`, and a service layer architecture (`InventoryService`) with atomic transactions.
- **Procedural Programming:** Pure, deterministic utility functions for strict data validation, stock status calculation, financial math, and currency formatting (`utils.py`).
- **Event-Driven Programming:** Client-side DOM event listeners (search debouncing, form validation, filter drawers, real-time live preview, projected balance calculations) and Flask's route-driven HTTP event handling.

---

## ✨ Key Capabilities

- **📊 Inventory Dashboard:**
  - **4 Unified KPI Cards:** Total Products, Total Stock Units, Low Stock Alerts, and Total Inventory Value (₹), styled with clean white surfaces, subtle borders, and dedicated icon containers.
  - **7-Day Stock Movement Visualization:** Pure CSS responsive grouped bar chart comparing daily Stock In (receipts) vs. Stock Out (issues) based on verified audit records.
  - **Inventory Health Donut Gauge:** Inline SVG proportional donut visualization tracking Healthy, Low Stock, and Out of Stock inventory percentages.
  - **Stock Alerts List:** Immediate restock links for low-stock and out-of-stock items, with priority badges.
  - **Recent Movement Log:** Compact, high-density table displaying the latest inventory movements.

- **📋 Complete Product Catalog Management:**
  - Full CRUD lifecycle: Create, Read, Update, and soft-delete (Archive) catalog items.
  - **Non-Destructive Archiving:** Soft-deletes products to preserve historical transactions and audit integrity.
  - **Live Product Form Preview:** Interactive real-time card preview on the Add/Edit form displaying product title, Product Code (SKU), price, stock status, and reorder levels as you type.
  - **Search & Filter Bar:** Single-row unified toolbar with debounced search (500ms), category selector, stock status filter, and multi-criteria sorting (Newest, Oldest, Name, Price, Quantity).
  - Server-side & client-side validation enforcing non-negative prices, integer quantities, and unique SKU constraints.

- **📥 Dual-Action Stock Console:**
  - **Segmented Tab Switcher:** Toggle between **Stock In** (supplier receipts/returns) and **Stock Out** (sales/issues/shrinkage) in a single unified workspace.
  - **Live Product Inspector:** Instantly inspects the selected product's current stock, reorder threshold, and visual meter gauge.
  - **Dynamic Projected Balance Calculator:** Computes the projected balance (`Current Stock ± Transaction Quantity`) in real-time as the user inputs values, providing instant visual feedback.
  - **Atomic Database Transactions:** Stock balance adjustments and immutable transaction log entries succeed or fail together as a single atomic unit.

- **🔄 Comprehensive Transaction History & Audit Log:**
  - Complete chronological audit log of all inventory movements (`OPENING`, `STOCK_IN`, `STOCK_OUT`).
  - Records reference ID, product name, SKU, movement type, quantity change (`+` / `-`), stock progression (`before → after`), and operator audit notes.
  - **Collapsible Filter Drawer:** Quick-access search and product filters with an expandable drawer for precise date range filtering (`Date From`, `Date To`, sort sequence).

- **📈 Analytical Reports & RFC 4180 CSV Export:**
  - Executive summary metric bar: Active SKUs, Total Units, Asset Value, Low Stock Alerts, and Stock Depletions.
  - Category valuation breakdown with percentage volume share indicators.
  - Zero-stock depletion table and low-stock reorder exception lists with one-click restock actions.
  - **Standardized CSV Exports:** Generates fully RFC 4180-compliant CSV files for both products and transaction logs using Python's built-in `csv.writer` with proper quoting and escaping.

- **⚙️ Settings & Configuration:**
  - System metadata, runtime parameters, Indian Rupee monetary formatting standards, and catalog taxonomy.
  - Documentation of automated low-stock and depletion threshold logic.

---

## 🛠 Technology Stack

| Layer | Technology | Details |
|---|---|---|
| **Frontend** | HTML5, CSS3, Vanilla JS | Custom responsive design system (1,700+ lines of CSS), CSS Grid/Flexbox, SVG line icons, zero external CDN dependencies |
| **Templates** | Jinja2 | Reusable master layout (`base.html`), modular page templates, custom formatting filters |
| **Backend** | Python 3 (Flask) | Lightweight WSGI web framework, RESTful routing, modular service architecture |
| **Database (local)** | SQLite3 | Default embedded database with foreign key enforcement |
| **Database (production)** | Neon PostgreSQL via `psycopg` | Connection-pooled access, parameterized queries, and row locks for stock mutations |
| **Testing** | `unittest` | SQLite unit/HTTP coverage plus PostgreSQL adapter and optional live concurrency coverage |

---

## 📁 Project Structure

```text
Stockly/
│
├── app.py                      # Flask routes, context processors, and HTTP controllers
├── database.py                 # SQLite / Neon PostgreSQL adapter and schema initialization
├── models.py                   # Domain models: Product and StockTransaction (OOP)
├── inventory_service.py        # Core business logic service with atomic transactions (OOP)
├── clock.py                    # Canonical India-local clock and SQLite timestamps
├── utils.py                    # Pure validation, calculation, and formatting utilities (Procedural)
├── seed.py                     # Idempotent database demonstration seeding script
├── requirements.txt            # Flask, psycopg binary package, and psycopg-pool
├── README.md                   # System documentation and setup guide
│
├── instance/
│   └── stockly.db              # SQLite persistent database (created on first run)
│
├── templates/
│   ├── base.html               # Master layout with dark navy sidebar and top utility bar
│   ├── dashboard.html          # Resource Management overview with KPI cards and charts
│   ├── products.html           # Product catalog with search, filter, and archive actions
│   ├── product_form.html       # 2-column Add/Edit product form with live interactive preview
│   ├── stock_management.html   # Segmented Stock In / Stock Out console with live inspector
│   ├── transactions.html       # Filterable audit log with collapsible date range drawer
│   ├── reports.html            # Inventory summary, alerts, category share, and CSV exports
│   └── settings.html           # System parameters, localization, and operational rules
│
├── static/
│   ├── css/
│   │   └── style.css           # 1,700+ lines of enterprise CSS (tokens, responsive, no CDNs)
│   └── js/
│       └── app.js              # Event-driven UI listeners (validation, debouncing, tab console)
│
├── tests/
│   ├── test_inventory.py       # SQLite unit and HTTP integration coverage
│   └── test_postgres_adapter.py # PostgreSQL adapter and concurrency coverage
│
└── docs/
    ├── architecture.md         # Multi-tiered architecture and paradigm mapping
    ├── flowchart.md             # Stock In/Out and Product lifecycle Mermaid flowcharts
    ├── assignment-report.md     # Structured programming-paradigms assignment report
    └── demo-presentation-outline.md
```

Stockly is a local-first academic application and is not intended for
unsecured public deployment.

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.9 or newer (tested on Python 3.10+)
- `pip` package manager

### 1. Clone or Open the Workspace
```bash
git clone https://github.com/md-suleiman/Stockly.git
cd Stockly
```

### 2. (Optional) Create and Activate Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# On Windows PowerShell:
.\venv\Scripts\Activate.ps1

# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Required Dependencies
```bash
pip install -r requirements.txt
```

### 4. Initialize & Populate Sample Data
Populate the database with realistic retail products across all categories and varying stock statuses:
```bash
python seed.py
```

The seed command creates nine natural retail products, including healthy,
low-stock, and out-of-stock inventory, plus a deterministic seven-calendar-day
history relative to the Asia/Kolkata date. Opening balances are kept in the
ledger but are not counted as Stock In on the dashboard chart. Timestamps use
canonical SQLite format `YYYY-MM-DD HH:MM:SS`; current-day sample timestamps are
clamped to the actual India-local seed time and future dates are never generated.
A hidden seed registry records
the dataset version and exact generated product/transaction IDs, making
repeated runs safe and allowing controlled rolling refreshes. Existing legacy
products and unmarked ledgers are preserved. A Product Code (SKU) means
“Stock Keeping Unit”: the unique internal code used to identify and track a
product.

### Production database (Neon PostgreSQL)

Local development does not require PostgreSQL: when `DATABASE_URL` is unset,
Stockly uses `instance/stockly.db`. In production, set `DATABASE_URL` to the
pooled Neon PostgreSQL connection string and optionally tune the small process
pool with `DATABASE_POOL_MAX_SIZE` (default: `5`). Do not commit either value.

```bash
# PowerShell example; use the pooled connection string from Neon.
$env:DATABASE_URL = 'postgresql://…'
$env:DATABASE_POOL_MAX_SIZE = '5'
$env:SECRET_KEY = 'replace-with-a-long-random-value'
python app.py
```

The application creates its schema on first use. Stock In and Stock Out run in
one transaction; on PostgreSQL the product row is read with `FOR UPDATE` before
the balance is calculated, preventing concurrent requests from overselling it.

### 5. Launch the Application
```bash
python app.py
```

Open your browser and navigate to:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🧪 Running Automated Tests

Run the full test suite using Python's built-in `unittest` runner:
```bash
python -m unittest discover -v
python -m unittest tests/test_inventory.py -v
```

The default suite exercises isolated temporary SQLite databases and PostgreSQL
adapter behavior. For a live PostgreSQL/Neon concurrency check, provision a
dedicated disposable test database (never production) and set `TEST_DATABASE_URL`:

```bash
# PowerShell
$env:TEST_DATABASE_URL = 'postgresql://…/stockly_test'
python -m unittest discover -v
```

The live test concurrently issues two stock-out requests and verifies that only
one succeeds. The suite verifies:
- Product creation, duplicate SKU rejection, price validation, and editing
- Soft-deletion (archiving) and preservation of historical records
- Atomic Stock In and Stock Out movements
- Stock Out rejection when quantity exceeds current availability
- Zero/negative movement input rejection
- Low-stock condition detection and inventory valuation calculations
- Inventory health distribution calculation (healthy, low stock, out of stock)
- 7-day movement data aggregation
- RFC 4180 standard CSV export formatting and escaping
- Defensive input validation (rejecting non-integer product IDs on stock endpoints)
- Cross-connection database persistence
- HTTP endpoints, HTML template rendering, and CSV exports

---

## 🎓 Programming Paradigms Mapping

| Paradigm | Implemented In | Demonstration in Code |
|---|---|---|
| **Object-Oriented Programming (OOP)** | `database.py`, `models.py`, `inventory_service.py` | Encapsulation of DB access; domain classes (`Product`, `StockTransaction`) with factory methods (`from_row`); Service layer pattern with dependency injection and atomic transaction management. |
| **Procedural Programming** | `utils.py` | Stateless, pure functions taking explicit inputs and returning clean outputs for validation (`validate_product_data`), computation (`calculate_inventory_value`), and formatting (`format_currency`). |
| **Event-Driven Programming** | `static/js/app.js`, `app.py` | Browser DOM event listeners (`input`, `change`, `submit`, `click`) controlling client interaction; Flask routes acting as HTTP request event handlers. |

For an in-depth architectural breakdown, refer to [docs/architecture.md](docs/architecture.md).  
For workflow diagrams, refer to [docs/flowchart.md](docs/flowchart.md).

---

## 🔒 Security & Deployment Scope

Stockly is architected as an offline-capable, local-first inventory management system suitable for small business operations, standalone retail counters, and educational demonstration:
- **Parameterization:** All database operations use strictly parameterized SQL queries (`?`) to prevent SQL injection vulnerabilities.
- **Data Integrity:** SQLite connections enable `PRAGMA foreign_keys = ON;`. PostgreSQL connections use a bounded `psycopg_pool` pool and lock the product row with `SELECT … FOR UPDATE` inside each stock mutation transaction.
- **Environment Configuration:** Flask's `SECRET_KEY` and debug modes are configurable via environment variables (`os.environ.get('SECRET_KEY')`), falling back to safe local development defaults.
- **Production Scope:** For multi-tenant or public cloud deployments, it is recommended to introduce session-based user authentication (e.g. Flask-Login or OAuth), CSRF protection tokens on all form submissions (e.g. Flask-WTF), and run Flask behind a production WSGI HTTP server (e.g. Gunicorn) with TLS/HTTPS.
