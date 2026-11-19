"""Seed a safe, natural-looking seven-day Stockly demonstration dataset."""

from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import os
import shutil

from database import Database


DATASET_KEY = 'stockly-demonstration'
DEMO_VERSION = 'historical-demo-v3'
LOCAL_ZONE = ZoneInfo('Asia/Kolkata')
STAMP_FORMAT = '%Y-%m-%d %H:%M:%S'
OLD_DEMO_SKUS = {
    'DEMO-ELE-WMOUSE', 'DEMO-ELE-USBC1M', 'DEMO-STA-NB200',
    'DEMO-HOM-WTRBOTL', 'DEMO-CLO-BKPACK', 'DEMO-GRO-RICE5K',
}
OLD_V1_SKUS = {
    'ELE-WMOUSE', 'ELE-USBC1M', 'ELE-LPSTND', 'STA-NB200',
    'STA-BPPEN10', 'HOM-WTRBOTL', 'CLO-BKPACK', 'ELE-HDPHN',
    'ELE-MCKBD', 'GRO-RICE5K', 'GRO-GTEA25', 'CLO-TSHRTM',
}
OLD_REASONS = {
    'Opening stock', 'Supplier delivery', 'Customer order fulfilled',
    'Restocking from warehouse', 'Walk-in customer purchase',
    'Bulk purchase received',
}

PRODUCTS = [
    ('Wireless Mouse', 'ELE-MOU-014', 'Electronics', 599.00, 18, 12),
    ('USB-C Cable (1m)', 'ELE-CAB-021', 'Electronics', 199.00, 42, 15),
    ('Mechanical Keyboard', 'ELE-KEY-009', 'Electronics', 3499.00, 7, 8),
    ('A4 Notebook', 'STA-NOT-008', 'Stationery', 85.00, 24, 20),
    ('Steel Water Bottle', 'HOM-WAT-006', 'Home & Living', 450.00, 0, 8),
    ('Canvas Backpack', 'CLO-BAG-011', 'Clothing', 1299.00, 16, 8),
    ('Basmati Rice (5 kg)', 'GRO-RIC-003', 'Grocery', 375.00, 31, 15),
    ('Bluetooth Speaker', 'ELE-SPK-017', 'Electronics', 2199.00, 9, 6),
    ('Printer Paper (500 sheets)', 'STA-PAP-012', 'Stationery', 420.00, 16, 10),
]

# Day offset from oldest date, SKU, type, quantity, visible operational reason.
MOVEMENTS = [
    (0, 'ELE-MOU-014', 'STOCK_IN', 20, 'Supplier delivery - PO-1042'),
    (0, 'ELE-CAB-021', 'STOCK_OUT', 12, 'Retail sale'),
    (0, 'STA-NOT-008', 'STOCK_OUT', 9, 'Customer order fulfilled'),
    (1, 'ELE-KEY-009', 'STOCK_IN', 14, 'Bulk stock received'),
    (1, 'ELE-CAB-021', 'STOCK_IN', 16, 'Warehouse replenishment'),
    (1, 'GRO-RIC-003', 'STOCK_OUT', 18, 'Store transfer'),
    (1, 'ELE-MOU-014', 'STOCK_OUT', 25, 'Retail sale'),
    (2, 'STA-NOT-008', 'STOCK_IN', 30, 'Supplier delivery - PO-1049'),
    (2, 'ELE-SPK-017', 'STOCK_IN', 12, 'Supplier delivery'),
    (2, 'GRO-RIC-003', 'STOCK_OUT', 14, 'Customer order fulfilled'),
    (2, 'CLO-BAG-011', 'STOCK_OUT', 8, 'Retail sale'),
    (3, 'HOM-WAT-006', 'STOCK_IN', 20, 'Warehouse replenishment'),
    (3, 'STA-PAP-012', 'STOCK_IN', 18, 'Supplier delivery'),
    (3, 'ELE-KEY-009', 'STOCK_OUT', 10, 'Customer order fulfilled'),
    (3, 'ELE-CAB-021', 'STOCK_OUT', 7, 'Retail sale'),
    (4, 'CLO-BAG-011', 'STOCK_IN', 16, 'Store transfer'),
    (4, 'GRO-RIC-003', 'STOCK_IN', 24, 'Bulk stock received'),
    (4, 'ELE-SPK-017', 'STOCK_OUT', 7, 'Retail sale'),
    (4, 'STA-NOT-008', 'STOCK_OUT', 12, 'Customer order fulfilled'),
    (5, 'ELE-MOU-014', 'STOCK_IN', 13, 'Supplier delivery - PO-1057'),
    (5, 'HOM-WAT-006', 'STOCK_OUT', 25, 'Retail sale'),
    (5, 'STA-PAP-012', 'STOCK_OUT', 8, 'Customer order fulfilled'),
    (6, 'ELE-CAB-021', 'STOCK_IN', 12, 'Warehouse replenishment'),
    (6, 'ELE-KEY-009', 'STOCK_OUT', 4, 'Retail sale'),
    (6, 'GRO-RIC-003', 'STOCK_OUT', 10, 'Customer order fulfilled'),
]


def _stamp(day, hour):
    return datetime.combine(day, time(hour, 0), tzinfo=LOCAL_ZONE).strftime(STAMP_FORMAT)


def _backup(path):
    if os.path.exists(path) and os.path.getsize(path):
        destination = f'{path}.pre-demo-v3'
        shutil.copy2(path, destination)
        return destination
    return None


def _ensure_registry(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS seed_registry (
            dataset_key TEXT PRIMARY KEY,
            version TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS seed_registry_products (
            dataset_key TEXT NOT NULL,
            product_id INTEGER PRIMARY KEY,
            FOREIGN KEY (dataset_key) REFERENCES seed_registry(dataset_key)
        );
        CREATE TABLE IF NOT EXISTS seed_registry_transactions (
            dataset_key TEXT NOT NULL,
            transaction_id INTEGER PRIMARY KEY,
            FOREIGN KEY (dataset_key) REFERENCES seed_registry(dataset_key)
        );
    ''')


def _old_seed_ids(conn):
    ids = []
    rows = conn.execute('SELECT product_id, sku FROM products').fetchall()
    for row in rows:
        if row['sku'] not in OLD_DEMO_SKUS:
            continue
        txns = conn.execute(
            'SELECT reason FROM stock_transactions WHERE product_id = ?',
            (row['product_id'],),
        ).fetchall()
        if all((t['reason'] or '').startswith('[DEMO]') or
               (t['reason'] or '') in OLD_REASONS for t in txns):
            ids.append(row['product_id'])
        elif txns:
            raise RuntimeError(
                f"Cannot migrate {row['sku']}: unmarked user transactions exist."
            )
    return ids


def _insert_product(conn, product, stamp):
    cursor = conn.execute(
        '''INSERT INTO products
           (sku, name, category, price, quantity, reorder_level, is_active,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)''',
        (product[1], product[0], product[2], product[3], product[4],
         product[5], stamp, stamp),
    )
    return cursor.lastrowid


def _create_dataset(conn, today):
    oldest = today - timedelta(days=6)
    target = {sku: quantity for _, sku, _, _, quantity, _ in PRODUCTS}
    for _, sku, movement_type, quantity, _ in MOVEMENTS:
        target[sku] += quantity if movement_type == 'STOCK_OUT' else -quantity

    product_ids = {}
    product_stamp = _stamp(today, 8)
    for product in PRODUCTS:
        product_ids[product[1]] = _insert_product(conn, product, product_stamp)

    transaction_ids = []
    for product in PRODUCTS:
        sku = product[1]
        current = target[sku]
        product_id = product_ids[sku]
        opening = conn.execute(
            '''INSERT INTO stock_transactions
               (product_id, transaction_type, quantity, stock_before,
                stock_after, reason, created_at)
               VALUES (?, 'OPENING', ?, 0, ?, 'Opening balance', ?)''',
            (product_id, current, current, _stamp(oldest, 7)),
        ).lastrowid
        transaction_ids.append(opening)
        for offset, move_sku, move_type, quantity, reason in MOVEMENTS:
            if move_sku != sku:
                continue
            before = current
            current += quantity if move_type == 'STOCK_IN' else -quantity
            if current < 0:
                raise ValueError(f'negative balance for {sku}')
            transaction_id = conn.execute(
                '''INSERT INTO stock_transactions
                   (product_id, transaction_type, quantity, stock_before,
                    stock_after, reason, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (product_id, move_type, quantity, before, current, reason,
                 _stamp(oldest + timedelta(days=offset),
                        9 if move_type == 'STOCK_IN' else 15)),
            ).lastrowid
            transaction_ids.append(transaction_id)
        if current != product[4]:
            raise ValueError(f'final balance mismatch for {sku}')
        conn.execute(
            'UPDATE products SET quantity = ?, updated_at = ? WHERE product_id = ?',
            (current, _stamp(today, 18), product_id),
        )
    return product_ids, transaction_ids


def seed_database(db_path=None):
    db = Database(db_path)
    db.init_db()
    conn = db.get_connection()
    today = datetime.now(LOCAL_ZONE).date()
    try:
        _ensure_registry(conn)
        registered = conn.execute(
            'SELECT product_id FROM seed_registry_products WHERE dataset_key = ?',
            (DATASET_KEY,),
        ).fetchall()
        refresh = False
        if registered:
            expected = {(today - timedelta(days=i)).isoformat() for i in range(7)}
            actual = {
                row[0] for row in conn.execute(
                    '''SELECT DISTINCT substr(t.created_at, 1, 10)
                       FROM seed_registry_transactions r
                       JOIN stock_transactions t ON t.transaction_id = r.transaction_id
                       WHERE r.dataset_key = ? AND t.transaction_type != 'OPENING' ''',
                    (DATASET_KEY,),
                )
            }
            if actual == expected:
                print(f'Database: {db.db_path}')
                print('Operation: safe no-op; current dataset is valid.')
                return {'products_added': 0, 'transactions_added': 0}
            product_ids = [row['product_id'] for row in registered]
            placeholders = ','.join('?' for _ in product_ids)
            registered_txns = {
                row['transaction_id'] for row in conn.execute(
                    'SELECT transaction_id FROM seed_registry_transactions WHERE dataset_key = ?',
                    (DATASET_KEY,),
                )
            }
            mixed = conn.execute(
                f'''SELECT transaction_id FROM stock_transactions
                    WHERE product_id IN ({placeholders})''',
                product_ids,
            ).fetchall()
            if any(row['transaction_id'] not in registered_txns for row in mixed):
                raise RuntimeError(
                    'Seeded products contain user transactions; refusing a destructive refresh.'
                )
            _backup(db.db_path)
            conn.execute(
                f'DELETE FROM stock_transactions WHERE product_id IN ({placeholders})',
                product_ids,
            )
            conn.execute(
                f'DELETE FROM products WHERE product_id IN ({placeholders})',
                product_ids,
            )
            conn.execute('DELETE FROM seed_registry_products WHERE dataset_key = ?', (DATASET_KEY,))
            conn.execute('DELETE FROM seed_registry_transactions WHERE dataset_key = ?', (DATASET_KEY,))
            refresh = True

        old_ids = _old_seed_ids(conn)
        if old_ids:
            backup = _backup(db.db_path)
            placeholders = ','.join('?' for _ in old_ids)
            conn.execute(
                f'DELETE FROM stock_transactions WHERE product_id IN ({placeholders})',
                old_ids,
            )
            conn.execute(
                f'DELETE FROM products WHERE product_id IN ({placeholders})',
                old_ids,
            )
            operation = f'migrated legacy seed data; backup={backup}'
        else:
            operation = 'fresh seed'

        product_ids, transaction_ids = _create_dataset(conn, today)
        now = _stamp(today, 18)
        conn.execute(
            'INSERT OR REPLACE INTO seed_registry(dataset_key, version, created_at) VALUES (?, ?, ?)',
            (DATASET_KEY, DEMO_VERSION, now),
        )
        conn.executemany(
            'INSERT INTO seed_registry_products(dataset_key, product_id) VALUES (?, ?)',
            [(DATASET_KEY, value) for value in product_ids.values()],
        )
        conn.executemany(
            'INSERT INTO seed_registry_transactions(dataset_key, transaction_id) VALUES (?, ?)',
            [(DATASET_KEY, value) for value in transaction_ids],
        )
        conn.execute(
            'INSERT OR REPLACE INTO app_metadata(key, value) VALUES (?, ?)',
            ('demo_seed', DEMO_VERSION),
        )
        conn.commit()
        print(f'Database: {db.db_path}')
        print(f'Operation: {"rolling refresh" if refresh else operation}')
        print(f'Products added: {len(product_ids)}')
        print(f'Transactions created: {len(transaction_ids)}')
        print(f'Date range: {(today - timedelta(days=6)).isoformat()} through {today.isoformat()}')
        return {'products_added': len(product_ids), 'transactions_added': len(transaction_ids)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    seed_database()
