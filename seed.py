"""Create deterministic, historical Stockly demonstration data.

The seed is deliberately independent of the service layer so timestamps and
ledger balances can be created as one consistent SQLite transaction.
"""

from datetime import datetime, timedelta
import os
import shutil
import sqlite3

from database import Database


DEMO_VERSION = 'historical-demo-v1'
DEMO_MARKER = '[DEMO]'
LEGACY_REASONS = {
    'Opening stock',
    'Supplier delivery',
    'Customer order fulfilled',
    'Restocking from warehouse',
    'Walk-in customer purchase',
    'Bulk purchase received',
}

PRODUCTS = [
    ('Wireless Mouse', 'ELE-WMOUSE', 'Electronics', 599.00, 45, 10),
    ('USB-C Cable (1m)', 'ELE-USBC1M', 'Electronics', 199.00, 120, 20),
    ('Laptop Stand', 'ELE-LPSTND', 'Electronics', 1499.00, 8, 5),
    ('Spiral Notebook (200 pages)', 'STA-NB200', 'Stationery', 85.00, 200, 50),
    ('Ballpoint Pen Pack (10)', 'STA-BPPEN10', 'Stationery', 120.00, 5, 15),
    ('Stainless Steel Water Bottle', 'HOM-WTRBOTL', 'Home & Living', 450.00, 0, 10),
    ('Canvas Backpack', 'CLO-BKPACK', 'Clothing', 1299.00, 25, 8),
    ('Over-Ear Headphones', 'ELE-HDPHN', 'Electronics', 2499.00, 3, 5),
    ('Mechanical Keyboard', 'ELE-MCKBD', 'Electronics', 3499.00, 15, 5),
    ('Basmati Rice (5 kg)', 'GRO-RICE5K', 'Grocery', 375.00, 60, 20),
    ('Green Tea (25 bags)', 'GRO-GTEA25', 'Grocery', 150.00, 0, 10),
    ('Cotton T-Shirt (M)', 'CLO-TSHRTM', 'Clothing', 499.00, 40, 10),
]

# (day offset, sku, type, quantity, reason)
MOVEMENTS = [
    (0, 'ELE-WMOUSE', 'STOCK_IN', 12, 'Supplier delivery'),
    (0, 'ELE-USBC1M', 'STOCK_OUT', 7, 'Retail sale'),
    (1, 'ELE-LPSTND', 'STOCK_IN', 8, 'Warehouse replenishment'),
    (1, 'STA-NB200', 'STOCK_OUT', 15, 'Customer order'),
    (2, 'STA-BPPEN10', 'STOCK_IN', 3, 'Supplier delivery'),
    (2, 'STA-BPPEN10', 'STOCK_OUT', 8, 'Retail sale'),
    (2, 'HOM-WTRBOTL', 'STOCK_OUT', 4, 'Customer order'),
    (3, 'CLO-BKPACK', 'STOCK_OUT', 6, 'Customer order'),
    (3, 'ELE-HDPHN', 'STOCK_IN', 7, 'Supplier delivery'),
    (3, 'ELE-HDPHN', 'STOCK_OUT', 10, 'Retail sale'),
    (4, 'ELE-MCKBD', 'STOCK_OUT', 9, 'Customer order'),
    (4, 'GRO-RICE5K', 'STOCK_IN', 12, 'Warehouse replenishment'),
    (5, 'GRO-GTEA25', 'STOCK_OUT', 6, 'Retail sale'),
    (5, 'CLO-TSHRTM', 'STOCK_IN', 10, 'Supplier delivery'),
    (6, 'ELE-WMOUSE', 'STOCK_OUT', 5, 'Retail sale'),
    (6, 'ELE-USBC1M', 'STOCK_IN', 14, 'Warehouse replenishment'),
]


def _backup_database(db_path):
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return None
    backup_path = f'{db_path}.pre-demo-backup'
    shutil.copy2(db_path, backup_path)
    return backup_path


def _legacy_demo_products(conn):
    """Return legacy product IDs only when every ledger row is seed-generated."""
    ids = []
    for row in conn.execute(
        "SELECT product_id, sku FROM products WHERE sku IN ({})".format(
            ','.join('?' for _ in PRODUCTS)
        ),
        [p[1] for p in PRODUCTS],
    ):
        transactions = conn.execute(
            'SELECT reason FROM stock_transactions WHERE product_id = ?',
            (row['product_id'],),
        ).fetchall()
        if transactions and all((t['reason'] or '') in LEGACY_REASONS for t in transactions):
            ids.append(row['product_id'])
    return ids


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


def _seed_ledger(conn, product_ids, now):
    start = now - timedelta(days=6)
    balances = {sku: target for _, sku, _, _, target, _ in PRODUCTS}
    for _, sku, transaction_type, quantity, _ in MOVEMENTS:
        balances[sku] += quantity if transaction_type == 'STOCK_OUT' else -quantity

    for product in PRODUCTS:
        _, sku, _, _, target, _ = product
        opening = balances[sku]
        product_id = product_ids[sku]
        if opening:
            timestamp = (start + timedelta(hours=7)).isoformat(timespec='seconds')
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
            timestamp = (start + timedelta(days=day, hours=9 + day)).isoformat(timespec='seconds')
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
            (current, now.isoformat(timespec='seconds'), product_id),
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
        marker = conn.execute(
            'SELECT value FROM app_metadata WHERE key = ?', ('demo_seed',)
        ).fetchone()
        if marker and marker['value'] == DEMO_VERSION:
            print('Seed skipped: historical demo data is already present.')
            return {'products_added': 0, 'transactions_added': 0, 'products_skipped': len(PRODUCTS)}

        legacy_ids = _legacy_demo_products(conn)
        if legacy_ids:
            backup_path = _backup_database(db.db_path)
            placeholders = ','.join('?' for _ in legacy_ids)
            conn.execute(
                f'DELETE FROM stock_transactions WHERE product_id IN ({placeholders})',
                legacy_ids,
            )
            conn.execute(
                f'DELETE FROM products WHERE product_id IN ({placeholders})',
                legacy_ids,
            )

        existing = {
            row['sku']: row['product_id']
            for row in conn.execute('SELECT sku, product_id FROM products')
        }
        product_ids = {}
        for product in PRODUCTS:
            sku = product[1]
            if sku in existing:
                product_ids[sku] = existing[sku]
                skipped_products += 1
            else:
                product_ids[sku] = _insert_product(
                    conn, product, datetime.now().isoformat(timespec='seconds')
                )
                added_products += 1

        # A mixed ledger is never rewritten. It is safer to leave it untouched
        # than to fabricate a historical balance around user-created records.
        mixed = [
            sku for sku, product_id in product_ids.items()
            if conn.execute(
                'SELECT 1 FROM stock_transactions WHERE product_id = ? LIMIT 1',
                (product_id,),
            ).fetchone()
        ]
        untracked_existing = [
            sku for sku, product_id in product_ids.items()
            if sku in existing and sku not in mixed
        ]
        if untracked_existing:
            raise RuntimeError(
                'Existing demo SKUs have no identifiable seed ledger; no data '
                f'was changed for: {", ".join(untracked_existing)}'
            )
        if mixed:
            raise RuntimeError(
                'Demo SKUs already contain unmarked transactions; no historical '
                f'data was changed for: {", ".join(mixed)}'
            )

        now = datetime.now().replace(microsecond=0)
        _seed_ledger(conn, product_ids, now)
        added_transactions = conn.execute(
            "SELECT COUNT(*) FROM stock_transactions WHERE reason LIKE ?",
            (f'{DEMO_MARKER}%',),
        ).fetchone()[0]
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
    print(
        f'Seed complete: {added_products} products added, '
        f'{added_transactions} sample transactions added, '
        f'{skipped_products} products skipped.'
    )
    return {
        'products_added': added_products,
        'transactions_added': added_transactions,
        'products_skipped': skipped_products,
    }


if __name__ == '__main__':
    seed_database()
