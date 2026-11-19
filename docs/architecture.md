# Stockly — System Architecture & Paradigm Mapping

## 1. Multi-Tiered System Architecture

Stockly adopts a clean, layered architecture separating user interface presentation, HTTP request routing, business logic orchestration, domain modeling, and persistent data storage.

```
+-------------------------------------------------------------------------+
|                              Browser UI                                 |
|  - HTML5 Responsive Views (Jinja2 Templates)                            |
|  - Responsive UI Styling & Pure CSS Charts (style.css)                  |
|  - Client-Side Event Listeners & Dynamic DOM Updates (app.js)           |
+------------------------------------+------------------------------------+
                                     | HTTP Requests (GET / POST)
                                     v
+-------------------------------------------------------------------------+
|                        Flask Presentation Layer                         |
|  - app.py (Route definitions & HTTP Request Handlers)                   |
|  - Request parsing, flash messaging, session handling                   |
|  - Template rendering & CSV streaming                                   |
+------------------------------------+------------------------------------+
                                     | Service Calls
                                     v
+------------------------------------+------------------------------------+
|                      Service & Utility Layer                            |
|  - inventory_service.py (InventoryService OOP Business Logic)           |
|  - utils.py (Procedural validation, math, and string formatting)        |
+------------------+----------------------------------+-------------------+
                   |                                  |
                   v Models                           v Queries
+----------------------------------+ +------------------------------------+
|           Domain Models          | |       Database Access Layer        |
|  - models.py                     | |  - database.py (Database Class)    |
|    - Product Class               | |    - PRAGMA foreign_keys = ON      |
|    - StockTransaction Class      | |    - Row factory encapsulation     |
|    - Factory constructors        | |    - Connection lifecycle          |
+----------------------------------+ +-----------------+------------------+
                                                       |
                                                       v Parameterized SQL
                                     +------------------------------------+
                                     |          SQLite3 Database          |
                                     |  - instance/stockly.db             |
                                     |  - products table                  |
                                     |  - stock_transactions table        |
                                     +------------------------------------+
```

---

## 2. Request Lifecycle: Stock In / Stock Out Operation

To guarantee data consistency and audit integrity, all stock updates follow an atomic commit pattern:

1. **User Interaction:** The inventory staff selects a product, specifies a quantity, enters a remark, and submits the form via the browser.
2. **Client Event Handler (`app.js`):** Validates that a product is selected and that the entered quantity is a positive number.
3. **HTTP Controller (`app.py`):** The route `@app.route('/stock/in', methods=['POST'])` catches the request, extracts form values, and delegates execution to `InventoryService.stock_in()`.
4. **Procedural Validation (`utils.py`):** `validate_stock_movement()` evaluates business rules:
   - Does the product exist?
   - Is the product currently active?
   - Is the quantity a valid integer $> 0$?
   - For `STOCK_OUT`: is `quantity <= current_stock`?
5. **Atomic Execution (`inventory_service.py`):**
   - Calculates `stock_before` and `stock_after = stock_before ± quantity`.
   - Executes `UPDATE products SET quantity = ?, updated_at = ? WHERE product_id = ?`.
   - Executes `INSERT INTO stock_transactions (...) VALUES (...)`.
   - Commits both statements simultaneously via `conn.commit()`. If an exception occurs, a rollback is executed, ensuring zero partial updates.
6. **Response & View Rendering:** The controller flashes the result and redirects
   to Stock Management. This Post/Redirect/Get flow prevents a browser refresh
   from repeating the movement.

---

## 3. Programming Paradigms Demonstration

### A. Object-Oriented Programming (OOP)
Stockly actively leverages OOP to structure entities and enforce separation of concerns:

- **Encapsulation:** The `Database` class encapsulates SQLite connection management, path resolution, and configuration (`PRAGMA foreign_keys = ON`). Consumers interact with high-level `.get_connection()` calls without dealing with raw file handles.
- **Domain Modeling & Factories:** The `Product` and `StockTransaction` classes group properties and entity behavior together. Class methods like `Product.from_row(row)` implement the **Factory Pattern** to translate raw database rows into domain objects.
- **Service Layer Pattern:** `InventoryService` encapsulates all business operations (CRUD, stock movements, search filters, and analytics) and owns a `Database` instance via **composition** and **dependency injection**.

```python
# OOP: models.py - Domain encapsulation & Factory Pattern
class Product:
    def __init__(self, product_id, sku, name, category, price, quantity, reorder_level, ...):
        self.product_id = product_id
        self.sku = sku
        self.name = name
        self.price = float(price)
        self.quantity = int(quantity)
        self.reorder_level = int(reorder_level)

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        return cls(product_id=row['product_id'], sku=row['sku'], ...)

    def get_stock_status(self):
        if self.quantity == 0:
            return 'out_of_stock'
        elif self.quantity <= self.reorder_level:
            return 'low_stock'
        return 'in_stock'
```

### B. Procedural Programming
Implemented in `utils.py`, procedural routines are stateless, deterministic functions that take explicit arguments and return explicit results without mutating external state.

- **Data Validation:** `validate_product_data()` verifies product names, categories, price thresholds, and duplicate SKU detection.
- **Stock Movement Checks:** `validate_stock_movement()` validates requested stock movements against current inventory constraints.
- **Calculations & Aggregations:** `calculate_inventory_value()` and `calculate_total_stock_units()` calculate metrics across collections.
- **Formatting:** `format_currency()` converts numbers into Indian digit grouping (`₹1,23,456.78`).

```python
# Procedural: utils.py - Pure functions with explicit parameters
def calculate_inventory_value(products):
    """Computes total inventory value = sum(price * quantity) for active products."""
    return round(sum(p.price * p.quantity for p in products if p.is_active), 2)

def check_low_stock(product):
    """Determines whether a product is currently at or below reorder threshold."""
    return product.is_active and 0 < product.quantity <= product.reorder_level
```

### C. Event-Driven Programming
Stockly uses event-driven programming both on the client (browser events) and server (HTTP request events):

1. **Client-Side Event Listeners (`static/js/app.js`):**
   - `DOMContentLoaded`: Initializes listeners once the DOM is ready.
   - `input` event on search fields: Dispatches a debounced search submit after 600ms of typing inactivity.
   - `change` event on filters: Triggers instant form resubmission when the user selects a category or sorting order.
   - `change` event on Stock In/Out product selection: Updates a dynamic DOM badge displaying the item's live on-hand quantity.
   - `submit` event on forms: Intercepts submission to run client-side verification and confirm irreversible operations.
2. **Server-Side Event Driven Routing (`app.py`):**
   - Flask's WSGI framework matches incoming HTTP event triggers (`GET /products`, `POST /stock/in`) to dedicated callback handlers.

---

## 4. Paradigm Comparison Matrix in Stockly

| Feature | Object-Oriented Programming (OOP) | Procedural Programming | Event-Driven Programming |
|---|---|---|---|
| **Primary Unit** | Classes and Objects | Functions and Procedures | Events and Handlers |
| **State Handling** | Encapsulated within object attributes | Passed explicitly via parameters | Maintained in DOM state or session |
| **Location in Code** | `database.py`, `models.py`, `inventory_service.py` | `utils.py` | `static/js/app.js`, `app.py` |
| **Role in Stockly** | Entity models, database lifecycle, service orchestration | Mathematical logic, validation rules, string formatting | User interaction, search debounce, HTTP request routing |
| **Key Advantage** | High cohesion, maintainability, separation of concerns | Pure, easily testable logic without side effects | Responsive, interactive, non-blocking user experience |
