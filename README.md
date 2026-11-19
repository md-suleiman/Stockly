# 📦 Stockly — Inventory & Resource Management System

> **Smarter Stock. Simpler Management.**

**Academic Project Title:** Design and Development of Stockly – A Web-Based Inventory and Resource Management System  
**Domain:** Inventory Management  
**Target Users:** Small retail business owners and inventory staff  
**Currency:** Indian Rupees (₹)

---

## 📋 Overview

**Stockly** is a robust, production-grade, browser-based inventory and resource management web application designed for small retailers, shops, and enterprise inventory personnel. Built cleanly with Python, Flask, SQLite, and vanilla frontend technologies, Stockly eliminates complex cloud and third-party dependencies while delivering an intuitive, SaaS-style management dashboard.

Stockly genuinely illustrates core software engineering and programming paradigms:
- **Object-Oriented Programming (OOP):** Rich domain models (`Product`, `StockTransaction`), encapsulation of database access (`Database`), and the service layer architecture (`InventoryService`).
- **Procedural Programming:** Reusable, pure utility functions for strict data validation, status checking, calculations, and formatting (`utils.py`).
- **Event-Driven Programming:** Client-side user event listeners (search debouncing, form validation, filter updates, modal prompts) and Flask's route-driven HTTP event handling.

---

## ✨ Features

- **📊 Resource Management Dashboard:**
  - Real-time KPI summary cards: Total Products, Total Stock Units, Low Stock Alerts, and Total Inventory Value (₹).
  - Pure CSS horizontal bar charts displaying category-wise stock allocation.
  - Active low-stock alerts and recent stock transaction feed.
  - Quick action shortcuts for instant product addition and stock movements.

- **📋 Complete Product Management:**
  - Full CRUD operations: Create, Read, Update, and Archive products.
  - Non-destructive soft-delete (archiving) ensuring transaction history remains intact.
  - Server-side and client-side field validation (rejects negative prices, negative stock, and duplicate SKUs).
  - Search by SKU or product name with live debouncing.
  - Filtering by category (Electronics, Grocery, Stationery, Clothing, Home & Living, Other) and stock status.
  - Multi-criteria sorting (Newest, Oldest, Name, Price, Quantity).

- **📥 Dual-Action Stock Management:**
  - **Stock In:** Restock inventory with quantity, supplier details, and batch notes.
  - **Stock Out:** Issue or sell stock with pre-validation against available on-hand quantities.
  - Atomic database transactions: stock updates and audit transaction logs succeed or fail together.

- **🔄 Comprehensive Transaction History:**
  - Complete chronological audit log of all inventory movements (`OPENING`, `STOCK_IN`, `STOCK_OUT`).
  - Records previous stock, movement quantity, updated stock, timestamp, and remark notes.
  - Filterable by product, movement type, date range, and search terms.

- **📈 Analytical Reports & Data Export:**
  - Low-stock and out-of-stock item tracking.
  - Category-level quantity and valuation breakdowns.
  - Instant CSV export for both products and transaction logs.

- **⚙️ Settings & System Information:**
  - System metadata, currency standards, and operational guidelines on reorder thresholds.

---

## 🛠 Technology Stack

| Layer | Technology | Description |
|---|---|---|
| **Frontend** | HTML5, CSS3, Vanilla JS | Modern SaaS styling with CSS Grid/Flexbox, responsive layout, pure CSS charts |
| **Templates** | Jinja2 | Reusable base layout, dynamic inheritance, custom formatting filters |
| **Backend** | Python 3 (Flask) | Lightweight WSGI web framework, RESTful routing, modular services |
| **Database** | SQLite3 | Embedded ACID-compliant database with foreign key enforcement and parameterization |
| **Testing** | `unittest` | 25 automated unit and HTTP integration test cases |

---

## 📁 Project Structure

```text
Stockly/
│
├── app.py                      # Flask routes and HTTP request controllers
├── database.py                 # SQLite connection manager and schema initialization (OOP)
├── models.py                   # Domain models: Product and StockTransaction (OOP)
├── inventory_service.py        # Core business logic service with atomic transactions (OOP)
├── utils.py                    # Reusable validation, math, and formatting functions (Procedural)
├── seed.py                     # Idempotent database demonstration seeding script
├── requirements.txt            # Minimal Python dependencies (Flask)
├── README.md                   # System documentation and setup guide
│
├── instance/
│   └── stockly.db              # SQLite persistent database (created on startup)
│
├── templates/
│   ├── base.html               # Master layout with dark navy sidebar and notifications
│   ├── dashboard.html          # Resource Management overview with KPI cards and charts
│   ├── products.html           # Product catalog with search, filter, and archive actions
│   ├── product_form.html       # Dynamic Add / Edit product form
│   ├── stock_management.html   # Dedicated Stock In and Stock Out interface
│   ├── transactions.html       # Filterable audit log of stock movements
│   ├── reports.html            # Inventory summary, alerts, and CSV export options
│   └── settings.html           # Application configuration and metadata
│
├── static/
│   ├── css/
│   │   └── style.css           # 1,200+ lines of custom CSS (SaaS theme, responsive, no CDNs)
│   └── js/
│       └── app.js              # Event-driven UI listeners (validation, debouncing, modals)
│
├── tests/
│   └── test_inventory.py       # Comprehensive unit and integration test suite
│
└── docs/
    ├── architecture.md         # Multi-tiered architecture and paradigm mapping
    └── flowchart.md            # Stock In/Out and Product lifecycle Mermaid flowcharts
```

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.8 or newer (tested on Python 3.10+)
- `pip` package manager

### 1. Clone or Open the Workspace
```powershell
cd c:\Users\suneh\OneDrive\Desktop\Projects\Stockly
```

### 2. (Optional) Create and Activate Virtual Environment
```powershell
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate
```

### 3. Install Required Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Initialize & Populate Sample Data
Populate the database with realistic retail products across all categories and varying stock statuses:
```powershell
python seed.py
```
*(The seed script is safe to run multiple times without duplicating data).*

### 5. Launch the Application
```powershell
python app.py
```

Open your browser and navigate to:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🧪 Running Automated Tests

Run the full test suite using Python's built-in `unittest` runner:
```powershell
python -m unittest tests/test_inventory.py -v
```

All 25 automated tests execute against an isolated temporary SQLite database, verifying:
- Product creation, duplicate SKU rejection, price validation, and editing
- Soft-deletion (archival) and preservation of historical records
- Atomic Stock In and Stock Out movements
- Stock Out rejection when quantity exceeds current availability
- Zero/negative movement input rejection
- Low-stock condition detection and inventory valuation calculations
- Cross-connection database persistence
- HTTP endpoints, HTML template rendering, and CSV exports

---

## 🎓 Programming Paradigms Mapping

| Paradigm | Implemented In | Demonstration in Code |
|---|---|---|
| **Object-Oriented Programming (OOP)** | `database.py`, `models.py`, `inventory_service.py` | Encapsulation of DB access; domain classes (`Product`, `StockTransaction`) with factory methods (`from_row`); Service layer pattern with dependency injection. |
| **Procedural Programming** | `utils.py` | Stateless, pure functions taking explicit inputs and returning clean outputs for validation (`validate_product_data`), computation (`calculate_inventory_value`), and formatting (`format_currency`). |
| **Event-Driven Programming** | `static/js/app.js`, `app.py` | Browser DOM event listeners (`input`, `change`, `submit`, `click`) controlling client interaction; Flask routes acting as HTTP request event handlers. |

For an in-depth architectural breakdown, refer to [docs/architecture.md](docs/architecture.md).  
For workflow diagrams, refer to [docs/flowchart.md](docs/flowchart.md).

