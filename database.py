"""Database adapter: Neon PostgreSQL in production, SQLite locally."""

import os
import re
import sqlite3
import threading

_POOL = None
_POOL_LOCK = threading.Lock()


class _Row:
    """Small sqlite3.Row-compatible wrapper for psycopg dictionary rows."""
    def __init__(self, mapping):
        self._mapping = dict(mapping)
        self._values = list(self._mapping.values())

    def __getitem__(self, key):
        return self._values[key] if isinstance(key, int) else self._mapping[key]

    def keys(self):
        return self._mapping.keys()

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)


class _Cursor:
    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def fetchone(self):
        row = self._cursor.fetchone()
        return _Row(row) if row is not None else None

    def fetchall(self):
        return [_Row(row) for row in self._cursor.fetchall()]


class _PostgresConnection:
    """Expose the subset of sqlite's connection API used by Stockly."""
    _INSERT_KEYS = {'products': 'product_id', 'stock_transactions': 'transaction_id'}

    def __init__(self, pool, connection):
        self._pool = pool
        self._connection = connection
        self._returned = False

    @staticmethod
    def _translate(sql):
        statement = sql.strip()
        if re.fullmatch(r'BEGIN\s+IMMEDIATE', statement, flags=re.IGNORECASE):
            return 'BEGIN'
        statement = re.sub(
            r"datetime\s*\(\s*replace\(([^,]+),\s*'T',\s*' '\)\s*\)",
            r"replace(\1, 'T', ' ')::timestamp", statement, flags=re.IGNORECASE,
        )
        statement = re.sub(
            r'INSERT\s+OR\s+REPLACE\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*(\([^;]+\))',
            lambda match: (
                f"INSERT INTO {match.group(1)} ({match.group(2)}) VALUES {match.group(3)} "
                f"ON CONFLICT ({match.group(2).split(',')[0].strip()}) DO UPDATE SET "
                + ', '.join(
                    f"{column.strip()} = EXCLUDED.{column.strip()}"
                    for column in match.group(2).split(',')[1:]
                )
            ),
            statement,
            flags=re.IGNORECASE,
        )
        return statement.replace('?', '%s')

    @classmethod
    def _insert_key(cls, statement):
        match = re.match(r'INSERT\s+INTO\s+([a-z_]+)', statement, flags=re.IGNORECASE)
        return cls._INSERT_KEYS.get(match.group(1).lower()) if match else None

    def execute(self, sql, params=()):
        statement = self._translate(sql)
        key = self._insert_key(statement)
        needs_returning = key and 'RETURNING' not in statement.upper()
        if needs_returning:
            statement = f'{statement.rstrip().rstrip(";")} RETURNING {key}'
        cursor = self._connection.execute(statement, params)
        lastrowid = cursor.fetchone()[key] if needs_returning else None
        return _Cursor(cursor, lastrowid)

    def executemany(self, sql, params_seq):
        cursor = self._connection.cursor()
        cursor.executemany(self._translate(sql), params_seq)
        return _Cursor(cursor)

    def executescript(self, sql):
        with self._connection.cursor() as cursor:
            cursor.execute(self._translate(
                sql.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'BIGSERIAL PRIMARY KEY')
                .replace('REAL', 'DOUBLE PRECISION')
            ))

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        if not self._returned:
            self._pool.putconn(self._connection)
            self._returned = True


class Database:
    """Keep the SQLite development path intact while pooling production DB access."""
    SQLITE_SCHEMA = '''
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL, category TEXT NOT NULL, price REAL NOT NULL CHECK(price >= 0),
            quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
            reorder_level INTEGER NOT NULL DEFAULT 0 CHECK(reorder_level >= 0),
            is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS stock_transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL,
            transaction_type TEXT NOT NULL CHECK(transaction_type IN ('STOCK_IN','STOCK_OUT','OPENING')),
            quantity INTEGER NOT NULL CHECK(quantity > 0), stock_before INTEGER NOT NULL,
            stock_after INTEGER NOT NULL, reason TEXT, created_at TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
        CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
        CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
        CREATE INDEX IF NOT EXISTS idx_products_is_active ON products(is_active);
        CREATE INDEX IF NOT EXISTS idx_txn_product_id ON stock_transactions(product_id);
        CREATE INDEX IF NOT EXISTS idx_txn_type ON stock_transactions(transaction_type);
        CREATE INDEX IF NOT EXISTS idx_txn_created_at ON stock_transactions(created_at);
        CREATE TABLE IF NOT EXISTS app_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    '''
    POSTGRES_SCHEMA = SQLITE_SCHEMA.replace(
        'INTEGER PRIMARY KEY AUTOINCREMENT', 'BIGSERIAL PRIMARY KEY'
    ).replace('REAL', 'DOUBLE PRECISION')
    SCHEMA_SQL = SQLITE_SCHEMA

    def __init__(self, db_path=None):
        self.database_url = os.environ.get('DATABASE_URL') if db_path is None else None
        self.using_postgres = bool(self.database_url)
        self.supports_row_locking = self.using_postgres
        if not self.using_postgres:
            if db_path is None:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                instance_dir = os.path.join(base_dir, 'instance')
                os.makedirs(instance_dir, exist_ok=True)
                self.db_path = os.path.join(instance_dir, 'stockly.db')
            else:
                parent = os.path.dirname(os.path.abspath(db_path))
                if parent:
                    os.makedirs(parent, exist_ok=True)
                self.db_path = db_path

    def _pool(self):
        global _POOL
        if _POOL is None:
            with _POOL_LOCK:
                if _POOL is None:
                    from psycopg.rows import dict_row
                    from psycopg_pool import ConnectionPool
                    _POOL = ConnectionPool(
                        conninfo=self.database_url, min_size=1,
                        max_size=int(os.environ.get('DATABASE_POOL_MAX_SIZE', '5')),
                        kwargs={'row_factory': dict_row}, open=True,
                    )
        return _POOL

    def get_connection(self):
        if self.using_postgres:
            pool = self._pool()
            return _PostgresConnection(pool, pool.getconn())
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    def init_db(self):
        conn = self.get_connection()
        try:
            conn.executescript(self.POSTGRES_SCHEMA if self.using_postgres else self.SQLITE_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def __repr__(self):
        return 'Database(postgresql)' if self.using_postgres else f"Database(path='{self.db_path}')"
