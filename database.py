"""
Database Module for Stockly
============================
PROGRAMMING PARADIGM: Object-Oriented Programming (OOP)

This module demonstrates OOP through the Database class, which encapsulates
all database connection management, schema creation, and lifecycle operations.
Internal connection details are hidden from the rest of the application.
"""

import sqlite3
import os


class Database:
    """
    OOP Concept: Encapsulation
    ---------------------------
    The Database class encapsulates SQLite connection management and schema
    initialization. Callers interact with a clean interface (get_connection,
    init_db) without knowledge of file paths or PRAGMA settings.
    """

    # -- OOP Concept: Class-level constants (shared across all instances) --
    SCHEMA_SQL = '''
        CREATE TABLE IF NOT EXISTS products (
            product_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            sku           TEXT    UNIQUE NOT NULL,
            name          TEXT    NOT NULL,
            category      TEXT    NOT NULL,
            price         REAL    NOT NULL CHECK(price >= 0),
            quantity       INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
            reorder_level INTEGER NOT NULL DEFAULT 0 CHECK(reorder_level >= 0),
            is_active     INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT    NOT NULL,
            updated_at    TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS stock_transactions (
            transaction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id       INTEGER NOT NULL,
            transaction_type TEXT    NOT NULL
                             CHECK(transaction_type IN ('STOCK_IN','STOCK_OUT','OPENING')),
            quantity          INTEGER NOT NULL CHECK(quantity > 0),
            stock_before     INTEGER NOT NULL,
            stock_after      INTEGER NOT NULL,
            reason           TEXT,
            created_at       TEXT    NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );

        CREATE INDEX IF NOT EXISTS idx_products_sku        ON products(sku);
        CREATE INDEX IF NOT EXISTS idx_products_category    ON products(category);
        CREATE INDEX IF NOT EXISTS idx_products_is_active   ON products(is_active);
        CREATE INDEX IF NOT EXISTS idx_txn_product_id       ON stock_transactions(product_id);
        CREATE INDEX IF NOT EXISTS idx_txn_type             ON stock_transactions(transaction_type);
        CREATE INDEX IF NOT EXISTS idx_txn_created_at       ON stock_transactions(created_at);

        CREATE TABLE IF NOT EXISTS app_metadata (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    '''

    def __init__(self, db_path=None):
        """
        OOP Concept: Constructor with sensible defaults.
        If no path is given, default to instance/stockly.db relative to this file.
        """
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            instance_dir = os.path.join(base_dir, 'instance')
            os.makedirs(instance_dir, exist_ok=True)
            self.db_path = os.path.join(instance_dir, 'stockly.db')
        else:
            # Ensure parent directory exists for custom paths too
            parent = os.path.dirname(os.path.abspath(db_path))
            if parent:
                os.makedirs(parent, exist_ok=True)
            self.db_path = db_path

    def get_connection(self):
        """
        Create and return a new database connection.
        Foreign-key enforcement and Row factory are enabled on every connection.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self):
        """Create tables and indexes if they do not already exist."""
        conn = self.get_connection()
        try:
            conn.executescript(self.SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    def __repr__(self):
        return f"Database(path='{self.db_path}')"
