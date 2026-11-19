"""Create deterministic, historical Stockly demonstration data.

The seed is deliberately independent of the service layer so timestamps and
ledger balances can be created as one consistent SQLite transaction.
"""

from datetime import date, datetime, time, timedelta
import os
import shutil

from database import Database


DEMO_VERSION = 'historical-demo-v2'
DEMO_MARKER = '[DEMO]'

PRODUCTS = [
    ('Demo Wireless Mouse', 'DEMO-ELE-WMOUSE', 'Electronics', 599.00, 45, 10),
    ('Demo USB-C Cable (1m)', 'DEMO-ELE-USBC1M', 'Electronics', 199.00, 120, 20),
    ('Demo Spiral Notebook', 'DEMO-STA-NB200', 'Stationery', 85.00, 200, 50),
    ('Demo Water Bottle', 'DEMO-HOM-WTRBOTL', 'Home & Living', 450.00, 18, 10),
    ('Demo Canvas Backpack', 'DEMO-CLO-BKPACK', 'Clothing', 1299.00, 25, 8),
    ('Demo Basmati Rice', 'DEMO-GRO-RICE5K', 'Grocery', 375.00, 60, 20),
]

# (day offset from oldest date, sku, type, quantity, reason)
MOVEMENTS = [
    (0, 'DEMO-ELE-WMOUSE', 'STOCK_IN', 8, 'Supplier delivery'),
    (0, 'DEMO-ELE-USBC1M', 'STOCK_OUT', 5, 'Retail sale'),
    (1, 'DEMO-ELE-USBC1M', 'STOCK_IN', 22, 'Warehouse replenishment'),
    (1, 'DEMO-STA-NB200', 'STOCK_OUT', 11, 'Customer order'),
    (2, 'DEMO-STA-NB200', 'STOCK_IN', 35, 'Supplier delivery'),
    (2, 'DEMO-HOM-WTRBOTL', 'STOCK_OUT', 4, 'Retail sale'),
    (3, 'DEMO-HOM-WTRBOTL', 'STOCK_IN', 18, 'Warehouse replenishment'),
    (3, 'DEMO-CLO-BKPACK', 'STOCK_OUT', 7, 'Customer order'),
    (4, 'DEMO-CLO-BKPACK', 'STOCK_IN', 16, 'Supplier delivery'),
    (4, 'DEMO-GRO-RICE5K', 'STOCK_OUT', 13, 'Retail sale'),
    (5, 'DEMO-GRO-RICE5K', 'STOCK_IN', 28, 'Supplier delivery'),
    (5, 'DEMO-ELE-WMOUSE', 'STOCK_OUT', 6, 'Customer order'),
    (6, 'DEMO-ELE-WMOUSE', 'STOCK_IN', 14, 'Warehouse replenishment'),
    (6, 'DEMO-ELE-USBC1M', 'STOCK_OUT', 9, 'Retail sale'),
]


def _backup_database(db_path):
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return None
    backup_path = f'{db_path}.pre-demo-backup'
    shutil.copy2(db_path, backup_path)
    return backup_path


def _insert_product(conn, product, created_at):
    name, sku, category, price, quantity, reorder_level = product
    cursor = conn.execute(
        '''INSERT INTO products
           (sku, name, category, price, quantity, reorder_level, is_active,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)''',
        (sku, name, category, price, quantity, reorder_level, created_at, created_at),
    )
    return cursor.lastrowid


def _seed_ledger(conn, product_ids, today):
    balances = {sku: target for _, sku, _, _, target, _ in PRODUCTS}
    for _, sku, transaction_type, quantity, _ in MOVEMENTS:
        balances[sku] += quantity if transaction_type == 'STOCK_OUT' else -quantity

    for product in PRODUCTS:
        _, sku, _, _, target, _ = product
        opening = balances[sku]
        product_id = product_ids[sku]
        oldest_date = today - timedelta(days=6)
        timestamp = datetime.combine(oldest_date, time(7, 0)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(
            '''INSERT INTO stock_transactions
               (product_id, transaction_type, quantity, stock_before,
                stock_after, reason, created_at)
               VALUES (?, 'OPENING', ?, 0, ?, ?, ?)''',
            (product_id, opening, opening, f'{DEMO_MARKER} Opening balance', timestamp),
        )
        current = opening
        for day, move_sku, move_type, quantity, reason in MOVEMENTS:
            if move_sku != sku:
                continue
            before = current
            if move_type == 'STOCK_IN':
                current += quantity
            else:
                if quantity > current:
                    raise ValueError(f'negative demo balance for {sku}')
                current -= quantity
            movement_date = oldest_date + timedelta(days=day)
            timestamp = datetime.combine(
                movement_date, time(9 if move_type == 'STOCK_IN' else 15, 0)
            ).strftime('%Y-%m-%d %H:%M:%S')
            conn.execute(
                '''INSERT INTO stock_transactions
                   (product_id, transaction_type, quantity, stock_before,
                    stock_after, reason, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (product_id, move_type, quantity, before, current,
                 f'{DEMO_MARKER} {reason}', timestamp),
            )
        if current != target:
            raise ValueError(f'demo ledger mismatch for {sku}: {current} != {target}')
        conn.execute(
            'UPDATE products SET quantity = ?, updated_at = ? WHERE product_id = ?',
            (current, datetime.combine(today, time(18, 0)).strftime('%Y-%m-%d %H:%M:%S'), product_id),
        )


def seed_database(db_path=None):
    """Seed the database once and print a useful idempotency summary."""
    db = Database(db_path=db_path)
    db.init_db()
    conn = db.get_connection()
    added_products = 0
    added_transactions = 0
    skipped_products = 0
    backup_path = None
    try:
        existing = {
            row['sku']: row['product_id']
            for row in conn.execute(
                "SELECT sku, product_id FROM products WHERE sku LIKE 'DEMO-%'"
            )
        }
        existing_txns = sum(
            conn.execute(
                'SELECT COUNT(*) FROM stock_transactions WHERE product_id = ?',
                (product_id,),
            ).fetchone()[0]
            for product_id in existing.values()
        )
        marker = conn.execute(
            'SELECT value FROM app_metadata WHERE key = ?', ('demo_seed',)
        ).fetchone()
        if marker and marker['value'] == DEMO_VERSION and len(existing) == len(PRODUCTS):
            expected_dates = {
                (date.today() - timedelta(days=i)).isoformat() for i in range(7)
            }
            actual_dates = {
                row['txn_date'] for row in conn.execute(
                    """                    SELECT DISTINCT substr(t.created_at, 1, 10) AS txn_date
                       FROM stock_transactions t
                       JOIN products p ON p.product_id = t.product_id
                       WHERE p.sku LIKE 'DEMO-%'
                         AND t.transaction_type IN ('STOCK_IN', 'STOCK_OUT')"""
                )
            }
            if actual_dates == expected_dates and existing_txns >= len(MOVEMENTS):
                print(f'Database: {db.db_path}')
                print('Seed skipped: validated historical demo data is already present.')
                return {'products_added': 0, 'transactions_added': 0, 'products_skipped': len(PRODUCTS)}
        if existing:
            raise RuntimeError(
                'Dedicated DEMO-* products already exist but are incomplete or '
                'invalid; refusing to alter them or their transaction history.'
            )

        product_ids = {}
        for product in PRODUCTS:
            sku = product[1]
            if sku in existing:
                product_ids[sku] = existing[sku]
                skipped_products += 1
            else:
                product_ids[sku] = _insert_product(
                    conn, product, datetime.combine(date.today(), time(8, 0)).strftime('%Y-%m-%d %H:%M:%S')
                )
                added_products += 1

        before_transactions = conn.execute(
            "SELECT COUNT(*) FROM stock_transactions WHERE reason LIKE ?",
            (f'{DEMO_MARKER}%',),
        ).fetchone()[0]
        _seed_ledger(conn, product_ids, date.today())
        after_transactions = conn.execute(
            "SELECT COUNT(*) FROM stock_transactions WHERE reason LIKE ?",
            (f'{DEMO_MARKER}%',),
        ).fetchone()[0]
        added_transactions = after_transactions - before_transactions
        conn.execute(
            'INSERT OR REPLACE INTO app_metadata(key, value) VALUES (?, ?)',
            ('demo_seed', DEMO_VERSION),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    if backup_path:
        print(f'  Backup created: {backup_path}')
    print(f'Database: {db.db_path}')
    print(
        f'Seed complete: {added_products} products added, '
        f'{added_transactions} sample transactions added, '
        f'{skipped_products} products skipped.'
    )
    print(f'Date range: {(datetime.now().date() - timedelta(days=6)).isoformat()} through {datetime.now().date().isoformat()}')
    return {
        'products_added': added_products,
        'transactions_added': added_transactions,
        'products_skipped': skipped_products,
    }


if __name__ == '__main__':
    seed_database()
