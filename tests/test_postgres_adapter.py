"""PostgreSQL-specific adapter and transaction coverage.

Set TEST_DATABASE_URL to a disposable PostgreSQL/Neon test database to run the
live concurrency test. It must never point at the production database.
"""

import os
import threading
import unittest
from unittest.mock import patch

import database as database_module
from database import Database, _PostgresConnection
from inventory_service import InventoryService


class _RawCursor:
    rowcount = 1

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class _RawConnection:
    def __init__(self):
        self.calls = []

    def execute(self, statement, params=()):
        self.calls.append((statement, params))
        return _RawCursor()

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        pass

    def rollback(self):
        pass


class _Pool:
    def putconn(self, _connection):
        pass


class _ServiceCursor:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _ServiceConnection:
    def __init__(self, product):
        self.product = product
        self.calls = []
        self.committed = False

    def execute(self, statement, params=()):
        self.calls.append((statement, params))
        return _ServiceCursor(self.product if statement.startswith('SELECT') else None)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass


class _ServiceDatabase:
    supports_row_locking = True

    def __init__(self, product):
        self.connection = _ServiceConnection(product)

    def init_db(self):
        pass

    def get_connection(self):
        return self.connection


class TestPostgresAdapter(unittest.TestCase):
    def test_adapter_translates_sqlite_transaction_and_placeholders(self):
        raw = _RawConnection()
        adapter = _PostgresConnection(_Pool(), raw)

        adapter.execute('BEGIN IMMEDIATE')
        adapter.execute('SELECT * FROM products WHERE product_id = ?', (7,))

        self.assertEqual(raw.calls[0], ('BEGIN', ()))
        self.assertEqual(
            raw.calls[1],
            ('SELECT * FROM products WHERE product_id = %s', (7,)),
        )

    def test_adapter_translates_sqlite_seed_upsert(self):
        raw = _RawConnection()
        adapter = _PostgresConnection(_Pool(), raw)

        adapter.execute(
            'INSERT OR REPLACE INTO app_metadata(key, value) VALUES (?, ?)',
            ('seed', 'v1'),
        )

        self.assertEqual(
            raw.calls[0],
            ('INSERT INTO app_metadata (key, value) VALUES (%s, %s) '
             'ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value', ('seed', 'v1')),
        )

    def test_stock_mutations_lock_postgres_product_row_after_transaction_begins(self):
        product = {
            'product_id': 11, 'sku': 'LOCK-1', 'name': 'Lock Test',
            'category': 'Other', 'price': 1, 'quantity': 10,
            'reorder_level': 2, 'is_active': 1,
            'created_at': '2026-01-01 00:00:00', 'updated_at': '2026-01-01 00:00:00',
        }
        for operation in ('stock_in', 'stock_out'):
            with self.subTest(operation=operation):
                db = _ServiceDatabase(product)
                service = InventoryService(db)
                result = getattr(service, operation)(11, '1', 'concurrency test')

                self.assertTrue(result[0])
                self.assertEqual(db.connection.calls[0][0], 'BEGIN IMMEDIATE')
                self.assertEqual(
                    db.connection.calls[1][0],
                    'SELECT * FROM products WHERE product_id = ? FOR UPDATE',
                )
                self.assertTrue(db.connection.committed)


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'TEST_DATABASE_URL is not configured')
class TestPostgresLiveConcurrency(unittest.TestCase):
    """Runs against a dedicated disposable PostgreSQL database only."""

    def setUp(self):
        self.environment = patch.dict(os.environ, {'DATABASE_URL': os.environ['TEST_DATABASE_URL']})
        self.environment.start()
        database_module._POOL = None
        self.db = Database()
        self.db.init_db()
        self.service = InventoryService(self.db)
        conn = self.db.get_connection()
        try:
            conn.execute('DELETE FROM stock_transactions')
            conn.execute('DELETE FROM products')
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        conn = self.db.get_connection()
        try:
            conn.execute('DELETE FROM stock_transactions')
            conn.execute('DELETE FROM products')
            conn.commit()
        finally:
            conn.close()
        self.environment.stop()

    def test_concurrent_stock_out_cannot_oversell(self):
        product_id, errors = self.service.add_product({
            'name': 'Concurrent Product', 'sku': 'PG-LOCK-1', 'category': 'Other',
            'price': '1', 'quantity': '10', 'reorder_level': '2',
        })
        self.assertEqual(errors, [])
        barrier = threading.Barrier(2)
        outcomes = []

        def take_stock():
            barrier.wait()
            outcomes.append(self.service.stock_out(product_id, '7', 'concurrent test'))

        workers = [threading.Thread(target=take_stock) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()

        self.assertEqual(sum(result[0] for result in outcomes), 1)
        self.assertEqual(self.service.get_product(product_id).quantity, 3)
