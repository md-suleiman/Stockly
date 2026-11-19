# Stockly — Workflow Flowcharts

This document illustrates the operational logic and decision paths implemented in Stockly using Mermaid flowcharts.

---

## 1. Stock In Workflow

The Stock In operation increases inventory quantity and creates an audit transaction log in an atomic database commit.

```mermaid
flowchart TD
    Start([User Initiates Stock In]) --> SelectProduct[Select Product from Dropdown]
    SelectProduct --> InputData[Enter Quantity and Optional Reason]
    InputData --> ClientValidation{Client Validation: Valid Input?}
    
    ClientValidation -- No --> ShowClientError[Display Error Message on Screen] --> EndFail([Operation Aborted])
    ClientValidation -- Yes --> SubmitHTTP[POST /stock/in Form Submission]
    
    SubmitHTTP --> ServerValidation{Server Validation:<br/>Product ID provided?<br/>Quantity integer > 0?}
    ServerValidation -- No --> FlashValidationError[Flash error message] --> RedirectIn[Redirect to /stock?mode=in] --> EndFail
    
    ServerValidation -- Yes --> CheckProduct{Product Exists and Active?}
    CheckProduct -- No --> FlashInactiveError[Flash inactive or not found error] --> RedirectIn
    
    CheckProduct -- Yes --> BeginTxn[Begin SQLite Database Transaction]
    BeginTxn --> CalcStock[Calculate: stock_after = stock_before + quantity]
    CalcStock --> UpdateProduct[UPDATE products SET quantity = stock_after]
    UpdateProduct --> InsertTxn[INSERT INTO stock_transactions: type=STOCK_IN]
    
    InsertTxn --> CommitTxn{Commit Database Transaction}
    CommitTxn -- Success --> FlashSuccess[Flash success notification] --> RedirectInSuccess[Redirect to /stock?mode=in] --> EndSuccess([Operation Complete])
    CommitTxn -- Failure --> RollbackTxn[Rollback Database Transaction] --> FlashDBError[Flash database error] --> RedirectIn
```

---

## 2. Stock Out Workflow

The Stock Out operation decrements on-hand inventory while enforcing strict checks against overselling.

```mermaid
flowchart TD
    Start([User Initiates Stock Out]) --> SelectProduct[Select Product from Dropdown]
    SelectProduct --> DisplayCurrent[UI Displays Current Available Stock]
    DisplayCurrent --> InputData[Enter Quantity to Remove and Reason]
    InputData --> ClientValidation{Client Validation: Valid Input?}
    
    ClientValidation -- No --> ShowClientError[Display Error Message on Screen] --> EndFail([Operation Aborted])
    ClientValidation -- Yes --> SubmitHTTP[POST /stock/out Form Submission]
    
    SubmitHTTP --> ServerValidation{Server Validation:<br/>Product ID provided?<br/>Quantity integer > 0?}
    ServerValidation -- No --> FlashValidationError[Flash error message] --> RedirectOut[Redirect to /stock?mode=out] --> EndFail
    
    ServerValidation -- Yes --> CheckProduct{Product Exists and Active?}
    CheckProduct -- No --> FlashInactiveError[Flash inactive or not found error] --> RedirectOut
    
    CheckProduct -- Yes --> CheckStockAvailability{Requested Quantity <= Current Quantity?}
    CheckStockAvailability -- No --> FlashInsufficientError[Flash insufficient-stock error] --> RedirectOut
    
    CheckStockAvailability -- Yes --> BeginTxn[Begin SQLite Database Transaction]
    BeginTxn --> CalcStock[Calculate: stock_after = stock_before - quantity]
    CalcStock --> UpdateProduct[UPDATE products SET quantity = stock_after]
    UpdateProduct --> InsertTxn[INSERT INTO stock_transactions: type=STOCK_OUT]
    
    InsertTxn --> CommitTxn{Commit Database Transaction}
    CommitTxn -- Success --> FlashSuccess[Flash success notification] --> RedirectOutSuccess[Redirect to /stock?mode=out] --> EndSuccess([Operation Complete])
    CommitTxn -- Failure --> RollbackTxn[Rollback Database Transaction] --> FlashDBError[Flash database error] --> RedirectOut
```

---

## 3. Product Creation & Opening Stock Workflow

Product creation validates unique SKU constraints and logs an `OPENING` transaction if an initial stock quantity is provided.

```mermaid
flowchart TD
    Start([User Opens Add Product Form]) --> EnterFields[Enter Name, SKU, Category, Price, Quantity, Reorder Level]
    EnterFields --> ClientValidate{Client Check: Required Fields Present?}
    ClientValidate -- No --> ShowClientMsg[Highlight Missing Fields] --> EndFail([Form Not Submitted])
    ClientValidate -- Yes --> SubmitPOST[POST /products/add]
    
    SubmitPOST --> ServerVal{Server Procedural Validation:<br/>Non-empty Name?<br/>Valid Category?<br/>Price >= 0?<br/>Quantity >= 0?<br/>Reorder Level >= 0?}
    ServerVal -- Fail --> ReturnErrors[Render Form with Validation Error List] --> EndFail
    
    ServerVal -- Pass --> CheckSKU{Is SKU Unique in Database?}
    CheckSKU -- No --> ReturnDuplicateSKU[Return Error: SKU Already in Use] --> EndFail
    
    CheckSKU -- Yes --> BeginDB[Begin SQLite Transaction]
    BeginDB --> InsertProduct[INSERT INTO products]
    InsertProduct --> CheckOpeningStock{Opening Quantity > 0?}
    
    CheckOpeningStock -- Yes --> InsertOpeningTxn[INSERT INTO stock_transactions:<br/>type=OPENING, before=0, after=qty]
    CheckOpeningStock -- No --> CommitProduct[Commit Transaction]
    InsertOpeningTxn --> CommitProduct
    
    CommitProduct --> RedirectProducts[Flash Success & Redirect to /products] --> EndSuccess([Product Created])
```
