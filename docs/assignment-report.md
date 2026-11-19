# Design and Development of Stockly – A Web-Based Inventory and Resource Management System

## 1. Problem and objectives

Small retail teams need a reliable way to maintain product records, track stock
movements, and understand inventory health. Stockly provides a local-first
workspace for those tasks while keeping the data model auditable and simple.

## 2. Scope and target users

The application supports catalog maintenance, product archiving and restoration,
atomic Stock In/Out operations, transaction history, reports, CSV export, and a
dashboard. It is intended for a small warehouse, store counter, or coursework
demonstration; it is not intended for unsecured public deployment.

## 3. Technology stack and architecture

Stockly uses Flask, Jinja2, vanilla HTML/CSS/JavaScript, Python's `sqlite3`
module, and SQLite. Flask routes form the presentation layer, `InventoryService`
contains business rules, `Database` owns connections and schema setup, domain
classes represent products and transactions, and `utils.py` contains stateless
validation/calculation helpers.

## 4. Database design

`products` stores catalog identity, category, price, quantity, reorder level,
active state, and timestamps. `stock_transactions` stores immutable movement
records with before/after balances. Foreign keys, checks, indexes, and atomic
transactions protect consistency. The seed registry tracks only generated
dataset ownership and is not rendered or exported.

## 5. Programming paradigms

### A1.1 — Procedural and object-oriented programming

Procedural programming is effective for focused, stateless operations such as
validating form data, calculating inventory value, formatting Indian Rupee
amounts, and checking stock status. These functions are easy to test with
inputs and outputs and avoid unnecessary shared state.

Object-oriented programming is appropriate for entities and resources with
identity and behavior. `Product` and `StockTransaction` encapsulate domain
data, `Database` encapsulates SQLite connection policy, and
`InventoryService` groups inventory operations behind a stable interface.
This improves maintainability and makes dependency injection for isolated tests
straightforward.

In enterprise systems, procedural utilities are useful at boundaries and in
batch calculations, while domain objects and services organize long-lived
business concepts. A combination is preferable here: pure rules remain
reusable and testable, while the service and model classes keep persistence
and inventory workflows coherent. Procedural code can become difficult to
maintain when it accumulates shared state; OOP can become excessive when a
simple calculation is hidden behind unnecessary abstractions.

### A1.2 — Application implementation

The Flask application factory registers a Blueprint and injects an
`InventoryService`. Product lifecycle routes validate input before writes.
Stock In and Stock Out use `BEGIN IMMEDIATE`, update the product and insert a
transaction in one commit, then use Post/Redirect/Get. Reports and dashboard
values are calculated from SQLite rather than hardcoded.

### A1.3 — GUI

The GUI uses a dark navigation sidebar, a light workspace, compact cards,
responsive tables, breadcrumbs, forms, flash feedback, and a mobile drawer.
Client event handlers update the stock inspector and product preview without
replacing server-side validation. Add screenshots from the running application
at desktop and mobile widths when submitting the assignment; this repository
does not claim screenshots that were not captured.

## 6. Algorithms and workflows

Stock changes validate product state and a positive whole-number quantity,
calculate the new balance, update the product, and append an audit record
atomically. Dashboard movement totals group only `STOCK_IN` and `STOCK_OUT`
records by the last seven India-local calendar dates; `OPENING` records are
excluded.

## 7. Testing

Run:

```text
python -m unittest discover -v
python -m unittest tests/test_inventory.py -v
python -m compileall -q .
```

The final audited run executed 52 tests with 0 failures and 0 errors. Tests use
isolated temporary SQLite databases for application behavior and direct database
assertions for ledger, filters, exports, and seed safety.

## 8. Limitations and future improvements

The application has no authentication, hosted multi-user concurrency model, or
external backup service. A future version could add authenticated deployment,
role-based permissions, scheduled backups, and richer import validation.

## 9. Conclusion

Stockly demonstrates how procedural utilities, object-oriented domain and
service layers, and event-driven browser/HTTP interactions can form a small but
coherent inventory application.

## 10. References

- Python documentation: https://docs.python.org/3/
- Flask documentation: https://flask.palletsprojects.com/
- SQLite documentation: https://www.sqlite.org/docs.html
- MDN HTML, CSS, and JavaScript documentation: https://developer.mozilla.org/
