# Programming Paradigm Comparison

## A1.1 – Paradigm Comparison (5 marks)

### Procedural programming

Procedural programming organizes a solution as a sequence of procedures that
operate on explicit inputs and produce outputs. Its characteristics include
top-down control flow, focused functions, local state, and direct composition
of reusable operations.

**Advantages:** it is straightforward to read, easy to test in isolation, and
efficient for deterministic calculations. **Disadvantages:** shared data can
become difficult to manage as an application grows, and related behaviour may
become scattered across many functions.

### Object-oriented programming

Object-oriented programming organizes software around objects that combine
state with the behaviour that operates on that state. Its principles include
encapsulation, abstraction, composition, and polymorphism.

**Advantages:** domain concepts are easier to model, responsibilities are
localized, and composition supports maintainable growth. **Disadvantages:**
small tasks can require more structure, and poorly designed class hierarchies
can add unnecessary coupling.

### Comparison

| Concern | Procedural | Object-oriented |
|---|---|---|
| Unit of reuse | Function or procedure | Class, object, or composed service |
| State | Passed explicitly or held in local/module scope | Encapsulated by objects |
| Maintainability | Strong for small, deterministic tasks | Strong for evolving domain workflows |
| Reusability | Reusable pure utilities | Reusable domain objects and services |
| Enterprise example | Validation, formatting, financial calculations | Product models, database gateway, inventory service |

Stockly uses both approaches deliberately. The pure validation, calculations,
stock-status checks, and formatting helpers in `utils.py` are procedural
because they are deterministic and have no need to own state. `Product`,
`StockTransaction`, `Database`, and `InventoryService` are object-oriented
because they encapsulate domain data, persistence, and coordinated inventory
operations.

## A1.2 – Application Implementation (10 marks)

The Flask routes coordinate HTTP events, `InventoryService` provides the
business layer, and `Database` manages SQLite connections with foreign keys.
Stock changes are protected by a single `BEGIN IMMEDIATE` transaction that
updates the product and audit record together.

## A1.3 – GUI Design and Implementation (5 marks)

The interface uses Jinja templates, responsive CSS, inline SVG line icons, and
event-driven JavaScript. Search, filters, segmented stock operations, live
previews, validation feedback, and responsive navigation are implemented
without external UI frameworks or online assets.
