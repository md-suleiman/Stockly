"""
Inventory Service Module for Stockly
======================================
PROGRAMMING PARADIGM: Object-Oriented Programming (OOP)

The InventoryService class is the central business-logic layer. It mediates
between Flask routes and the configured database, performing validation, atomic
stock operations, and report generation. This follows the Service Pattern —
a common OOP architectural approach.
"""

import logging
from database import Database
from models import Product, StockTransaction
from utils import validate_product_data, validate_stock_movement
from clock import timestamp, today

logger = logging.getLogger(__name__)


class InventoryService:
    """
    OOP Concepts demonstrated:
      - Encapsulation: hides DB details behind high-level methods.
      - Single Responsibility: handles inventory business logic only.
      - Composition: owns a Database instance (has-a relationship).
    """

    def __init__(self, db=None):
        """
        OOP Concept: Dependency Injection
        Accept an external Database or create a default one.
        """
        self.db = db or Database()
        self.db.init_db()

    # ========================================================================
    # PRODUCT CRUD
    # ========================================================================

    def add_product(self, data):
        """
        Add a new product. If opening quantity > 0, record an OPENING transaction.
        Returns (product_id, errors). Errors is a list; empty means success.
        Uses an atomic transaction so quantity update and transaction record
        are committed together or not at all.
        """
        # Build SKU lookup for duplicate checking
        existing_skus = self._get_sku_map()
        errors = validate_product_data(data, existing_skus)
        if errors:
            return None, errors

        now = timestamp()
        name = data['name'].strip()
        sku = data['sku'].strip()
        category = data['category'].strip()
        price = float(data['price'])
        quantity = int(data.get('quantity', 0))
        reorder_level = int(data.get('reorder_level', 0))

        conn = self.db.get_connection()
        try:
            cursor = conn.execute(
                '''INSERT INTO products
                   (sku, name, category, price, quantity, reorder_level,
                    is_active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)''',
                (sku, name, category, price, quantity, reorder_level, now, now)
            )
            product_id = cursor.lastrowid

            # Record opening-stock transaction if quantity > 0
            if quantity > 0:
                conn.execute(
                    '''INSERT INTO stock_transactions
                       (product_id, transaction_type, quantity,
                        stock_before, stock_after, reason, created_at)
                       VALUES (?, 'OPENING', ?, 0, ?, 'Opening stock', ?)''',
                    (product_id, quantity, quantity, now)
                )

            conn.commit()
            return product_id, []
        except Exception:
            conn.rollback()
            logger.exception('Failed to add product')
            return None, ['Unable to save the product. Please try again.']
        finally:
            conn.close()

    def get_product(self, product_id):
        """Retrieve a single product by ID. Returns Product or None."""
        conn = self.db.get_connection()
        try:
            row = conn.execute(
                'SELECT * FROM products WHERE product_id = ?',
                (product_id,)
            ).fetchone()
            return Product.from_row(row)
        finally:
            conn.close()

    def get_all_products(self, include_archived=False):
        """Return a list of Product objects, optionally including archived."""
        conn = self.db.get_connection()
        try:
            if include_archived:
                rows = conn.execute(
                    'SELECT * FROM products ORDER BY created_at DESC'
                ).fetchall()
            else:
                rows = conn.execute(
                    'SELECT * FROM products WHERE is_active = 1 '
                    'ORDER BY created_at DESC'
                ).fetchall()
            return [Product.from_row(r) for r in rows]
        finally:
            conn.close()

    def update_product(self, product_id, data):
        """
        Update product details (not quantity — quantity changes go through
        stock_in / stock_out). Returns (success: bool, errors: list).
        """
        product = self.get_product(product_id)
        if product is None:
            return False, ['Product not found.']

        existing_skus = self._get_sku_map()
        errors = validate_product_data(data, existing_skus, current_product_id=product_id)
        if errors:
            return False, errors

        now = timestamp()
        conn = self.db.get_connection()
        try:
            conn.execute(
                '''UPDATE products
                   SET sku = ?, name = ?, category = ?, price = ?,
                       reorder_level = ?, updated_at = ?
                   WHERE product_id = ?''',
                (data['sku'].strip(), data['name'].strip(),
                 data['category'].strip(), float(data['price']),
                 int(data['reorder_level']), now, product_id)
            )
            conn.commit()
            return True, []
        except Exception:
            conn.rollback()
            logger.exception('Failed to update product %s', product_id)
            return False, ['Unable to update the product. Please try again.']
        finally:
            conn.close()

    def archive_product(self, product_id):
        """
        Soft-delete: set is_active = 0. Transaction history is preserved.
        Returns (success: bool, error_message: str or None).
        """
        product = self.get_product(product_id)
        if product is None:
            return False, 'Product not found.'

        now = timestamp()
        conn = self.db.get_connection()
        try:
            conn.execute(
                'UPDATE products SET is_active = 0, updated_at = ? '
                'WHERE product_id = ?',
                (now, product_id)
            )
            conn.commit()
            return True, None
        except Exception:
            conn.rollback()
            logger.exception('Failed to archive product %s', product_id)
            return False, 'Unable to archive the product. Please try again.'
        finally:
            conn.close()

    def restore_product(self, product_id):
        """Restore an archived product without changing quantity or history."""
        product = self.get_product(product_id)
        if product is None:
            return False, 'Product not found.'
        if product.is_active:
            return False, 'Product is already active.'
        conn = self.db.get_connection()
        try:
            conn.execute(
                'UPDATE products SET is_active = 1, updated_at = ? WHERE product_id = ?',
                (timestamp(), product_id),
            )
            conn.commit()
            return True, None
        except Exception:
            conn.rollback()
            logger.exception('Failed to restore product %s', product_id)
            return False, 'Unable to restore the product. Please try again.'
        finally:
            conn.close()

    # ========================================================================
    # STOCK OPERATIONS (atomic)
    # ========================================================================

    def stock_in(self, product_id, quantity_str, reason=''):
        """
        Increase stock. Atomic: quantity update + transaction record in one commit.
        Returns (success, message, updated_quantity).
        """
        conn = self.db.get_connection()
        try:
            conn.execute('BEGIN IMMEDIATE')
            lock_clause = ' FOR UPDATE' if self.db.supports_row_locking else ''
            row = conn.execute(
                f'SELECT * FROM products WHERE product_id = ?{lock_clause}', (product_id,)
            ).fetchone()
            product = Product.from_row(row)
            quantity, errors = validate_stock_movement(product, quantity_str, 'STOCK_IN')
            if errors:
                conn.rollback()
                return False, errors[0], None
            now = timestamp()
            stock_before = product.quantity
            stock_after = stock_before + quantity
            conn.execute(
                'UPDATE products SET quantity = ?, updated_at = ? '
                'WHERE product_id = ?',
                (stock_after, now, product_id)
            )
            conn.execute(
                '''INSERT INTO stock_transactions
                   (product_id, transaction_type, quantity,
                    stock_before, stock_after, reason, created_at)
                   VALUES (?, 'STOCK_IN', ?, ?, ?, ?, ?)''',
                (product_id, quantity, stock_before, stock_after,
                 reason.strip() or 'Stock received', now)
            )
            conn.commit()
            return True, f'Successfully added {quantity} units. New stock: {stock_after}.', stock_after
        except Exception:
            conn.rollback()
            logger.exception('Failed to stock in product %s', product_id)
            return False, 'Unable to record stock in. Please try again.', None
        finally:
            conn.close()

    def stock_out(self, product_id, quantity_str, reason=''):
        """
        Decrease stock. Atomic: quantity update + transaction record in one commit.
        Returns (success, message, updated_quantity).
        """
        conn = self.db.get_connection()
        try:
            conn.execute('BEGIN IMMEDIATE')
            lock_clause = ' FOR UPDATE' if self.db.supports_row_locking else ''
            row = conn.execute(
                f'SELECT * FROM products WHERE product_id = ?{lock_clause}', (product_id,)
            ).fetchone()
            product = Product.from_row(row)
            quantity, errors = validate_stock_movement(product, quantity_str, 'STOCK_OUT')
            if errors:
                conn.rollback()
                return False, errors[0], None
            now = timestamp()
            stock_before = product.quantity
            stock_after = stock_before - quantity
            conn.execute(
                'UPDATE products SET quantity = ?, updated_at = ? '
                'WHERE product_id = ?',
                (stock_after, now, product_id)
            )
            conn.execute(
                '''INSERT INTO stock_transactions
                   (product_id, transaction_type, quantity,
                    stock_before, stock_after, reason, created_at)
                   VALUES (?, 'STOCK_OUT', ?, ?, ?, ?, ?)''',
                (product_id, quantity, stock_before, stock_after,
                 reason.strip() or 'Stock issued', now)
            )
            conn.commit()
            return True, f'Successfully removed {quantity} units. New stock: {stock_after}.', stock_after
        except Exception:
            conn.rollback()
            logger.exception('Failed to stock out product %s', product_id)
            return False, 'Unable to record stock out. Please try again.', None
        finally:
            conn.close()

    # ========================================================================
    # SEARCH & FILTER
    # ========================================================================

    def search_products(self, query='', category='', status='',
                        sort_by='created_at', include_archived=False):
        """
        Search/filter/sort products. Returns list of Product objects.
        """
        conn = self.db.get_connection()
        try:
            sql = 'SELECT * FROM products WHERE 1=1'
            params = []

            if not include_archived:
                sql += ' AND is_active = 1'

            if query:
                sql += ' AND (LOWER(name) LIKE ? OR LOWER(sku) LIKE ?)'
                q = f'%{query.lower()}%'
                params.extend([q, q])

            if category:
                sql += ' AND category = ?'
                params.append(category)

            if status == 'in_stock':
                sql += ' AND quantity > reorder_level'
            elif status == 'low_stock':
                sql += ' AND quantity > 0 AND quantity <= reorder_level'
            elif status == 'out_of_stock':
                sql += ' AND quantity = 0'

            # Sort
            allowed_sorts = {
                'name': 'name ASC',
                'name_asc': 'name ASC',
                'name_desc': 'name DESC',
                'price': 'price ASC',
                'price_low': 'price ASC',
                'price_desc': 'price DESC',
                'price_high': 'price DESC',
                'quantity': 'quantity ASC',
                'qty_low': 'quantity ASC',
                'quantity_desc': 'quantity DESC',
                'qty_high': 'quantity DESC',
                'created_at': 'created_at DESC',
                'created_at_asc': 'created_at ASC',
                'newest': 'created_at DESC',
                'oldest': 'created_at ASC',
            }
            order = allowed_sorts.get(sort_by, 'created_at DESC')
            sql += f' ORDER BY {order}'

            rows = conn.execute(sql, params).fetchall()
            return [Product.from_row(r) for r in rows]
        finally:
            conn.close()

    # ========================================================================
    # TRANSACTIONS
    # ========================================================================

    def get_transactions(self, product_id=None, transaction_type=None,
                         date_from=None, date_to=None, search='',
                         sort_order='DESC'):
        """Retrieve transactions with optional filters. Returns list of StockTransaction."""
        conn = self.db.get_connection()
        try:
            sql = '''SELECT t.*, p.name, p.sku
                     FROM stock_transactions t
                     JOIN products p ON t.product_id = p.product_id
                     WHERE 1=1'''
            params = []

            if product_id:
                sql += ' AND t.product_id = ?'
                params.append(int(product_id))

            if transaction_type:
                sql += ' AND t.transaction_type = ?'
                params.append(transaction_type)

            if date_from:
                sql += " AND substr(replace(t.created_at, 'T', ' '), 1, 10) >= ?"
                params.append(date_from)

            if date_to:
                sql += " AND substr(replace(t.created_at, 'T', ' '), 1, 10) <= ?"
                params.append(date_to)

            if search:
                sql += ' AND (LOWER(p.name) LIKE ? OR LOWER(p.sku) LIKE ? OR LOWER(t.reason) LIKE ?)'
                q = f'%{search.lower()}%'
                params.extend([q, q, q])

            if str(sort_order).upper() in ('ASC', 'OLDEST'):
                sql += " ORDER BY datetime(replace(t.created_at, 'T', ' ')) ASC, t.transaction_id ASC"
            else:
                sql += " ORDER BY datetime(replace(t.created_at, 'T', ' ')) DESC, t.transaction_id DESC"

            rows = conn.execute(sql, params).fetchall()
            return [StockTransaction.from_row(r) for r in rows]
        finally:
            conn.close()

    # ========================================================================
    # DASHBOARD & REPORTS
    # ========================================================================

    def get_dashboard_data(self):
        """Return every dashboard panel using a single database connection.

        Keeping the reads together reduces serverless connection churn while
        retaining the existing public service methods for other pages/tests.
        """
        from datetime import timedelta
        current_day = today()
        dates = [current_day - timedelta(days=i) for i in range(6, -1, -1)]
        date_strings = [day.strftime('%Y-%m-%d') for day in dates]
        conn = self.db.get_connection()
        try:
            aggregate = conn.execute(
                '''SELECT COUNT(*) AS total_products,
                          COALESCE(SUM(quantity), 0) AS total_stock,
                          COALESCE(SUM(price * quantity), 0) AS total_value,
                          COALESCE(SUM(CASE WHEN quantity > 0 AND quantity <= reorder_level THEN 1 ELSE 0 END), 0) AS low_stock_count,
                          COALESCE(SUM(CASE WHEN quantity > reorder_level THEN 1 ELSE 0 END), 0) AS healthy_count,
                          COALESCE(SUM(CASE WHEN quantity = 0 THEN 1 ELSE 0 END), 0) AS out_of_stock_count
                   FROM products WHERE is_active = 1'''
            ).fetchone()
            total_active = aggregate['total_products']
            health_percent = int(round((aggregate['healthy_count'] / total_active) * 100)) if total_active else None
            alert_rows = conn.execute(
                '''SELECT * FROM products WHERE is_active = 1
                   AND quantity <= reorder_level
                   ORDER BY CASE WHEN quantity = 0 THEN 0 ELSE 1 END, quantity ASC, name ASC'''
            ).fetchall()
            recent_rows = conn.execute(
                '''SELECT t.*, p.name, p.sku FROM stock_transactions t
                   JOIN products p ON t.product_id = p.product_id
                   ORDER BY datetime(replace(t.created_at, 'T', ' ')) DESC,
                            t.transaction_id DESC LIMIT ?''', (6,)
            ).fetchall()
            movement_rows = conn.execute(
                '''SELECT substr(created_at, 1, 10) AS txn_date, transaction_type,
                          SUM(quantity) AS total_qty FROM stock_transactions
                   WHERE replace(substr(created_at, 1, 10), 'T', ' ') >= ?
                     AND replace(substr(created_at, 1, 10), 'T', ' ') <= ?
                     AND transaction_type IN ('STOCK_IN', 'STOCK_OUT')
                   GROUP BY substr(created_at, 1, 10), transaction_type''',
                (date_strings[0], date_strings[-1]),
            ).fetchall()
        finally:
            conn.close()

        movement_totals = {
            (row['txn_date'], row['transaction_type']): row['total_qty']
            for row in movement_rows
        }
        movement_days = []
        for day in dates:
            date_string = day.strftime('%Y-%m-%d')
            movement_days.append({
                'date': date_string,
                'label': day.strftime('%d %b'),
                'day_name': day.strftime('%a'),
                'stock_in': int(movement_totals.get((date_string, 'STOCK_IN'), 0) or 0),
                'stock_out': int(movement_totals.get((date_string, 'STOCK_OUT'), 0) or 0),
            })
        max_movement = max(
            (max(day['stock_in'], day['stock_out']) for day in movement_days),
            default=0,
        )
        for day in movement_days:
            day['stock_in_percentage'] = (
                round(day['stock_in'] / max_movement * 100, 2)
                if max_movement else 0
            )
            day['stock_out_percentage'] = (
                round(day['stock_out'] / max_movement * 100, 2)
                if max_movement else 0
            )
        movement_stats = {
            'days': movement_days,
            'max_movement': max_movement,
            'has_movement': max_movement > 0,
        }
        stats = {key: aggregate[key] for key in ('total_products', 'total_stock', 'low_stock_count', 'total_value')}
        health_stats = {
            'total_active': total_active, 'healthy_count': aggregate['healthy_count'],
            'low_stock_count': aggregate['low_stock_count'], 'out_of_stock_count': aggregate['out_of_stock_count'],
            'health_percent': health_percent, 'health_label': f'{health_percent}%' if health_percent is not None else 'N/A',
            'attention_count': aggregate['low_stock_count'] + aggregate['out_of_stock_count'],
        }
        return {
            'stats': stats, 'low_stock_products': [Product.from_row(row) for row in alert_rows],
            'recent_transactions': [StockTransaction.from_row(row) for row in recent_rows],
            'health_stats': health_stats, 'movement_stats': movement_stats,
        }

    def get_dashboard_stats(self):
        """
        Compute dashboard KPI metrics from the database.
        Returns a dict with total_products, total_stock, low_stock_count,
        total_value.
        """
        products = self.get_all_products(include_archived=False)
        from utils import (calculate_inventory_value,
                           calculate_total_stock_units,
                           count_low_stock_products)
        return {
            'total_products': len(products),
            'total_stock': calculate_total_stock_units(products),
            'low_stock_count': count_low_stock_products(products),
            'total_value': calculate_inventory_value(products),
        }

    def get_low_stock_products(self):
        """Products where quantity <= reorder_level AND quantity > 0 AND active."""
        conn = self.db.get_connection()
        try:
            rows = conn.execute(
                '''SELECT * FROM products
                   WHERE is_active = 1 AND quantity > 0
                         AND quantity <= reorder_level
                   ORDER BY quantity ASC'''
            ).fetchall()
            return [Product.from_row(r) for r in rows]
        finally:
            conn.close()

    def get_out_of_stock_products(self):
        """Active products with zero quantity."""
        conn = self.db.get_connection()
        try:
            rows = conn.execute(
                '''SELECT * FROM products
                   WHERE is_active = 1 AND quantity = 0
                   ORDER BY name ASC'''
            ).fetchall()
            return [Product.from_row(r) for r in rows]
        finally:
            conn.close()

    def get_category_breakdown(self):
        """Stock quantity and value grouped by category (active products only)."""
        conn = self.db.get_connection()
        try:
            rows = conn.execute(
                '''SELECT category,
                          COUNT(*) as product_count,
                          SUM(quantity) as total_quantity,
                          SUM(price * quantity) as total_value
                   FROM products
                   WHERE is_active = 1
                   GROUP BY category
                   ORDER BY total_value DESC'''
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_recent_transactions(self, limit=10):
        """Most recent transactions for the dashboard."""
        conn = self.db.get_connection()
        try:
            rows = conn.execute(
                '''SELECT t.*, p.name, p.sku
                   FROM stock_transactions t
                   JOIN products p ON t.product_id = p.product_id
                   ORDER BY datetime(replace(t.created_at, 'T', ' ')) DESC,
                            t.transaction_id DESC
                   LIMIT ?''',
                (limit,)
            ).fetchall()
            return [StockTransaction.from_row(r) for r in rows]
        finally:
            conn.close()

    def get_inventory_summary(self):
        """Comprehensive summary for the reports page."""
        products = self.get_all_products(include_archived=False)
        from utils import (calculate_inventory_value,
                           calculate_total_stock_units,
                           count_low_stock_products)
        return {
            'total_active_products': len(products),
            'total_units': calculate_total_stock_units(products),
            'total_value': calculate_inventory_value(products),
            'low_stock_count': count_low_stock_products(products),
            'out_of_stock_count': sum(1 for p in products if p.quantity == 0),
            'categories': self.get_category_breakdown(),
        }

    def get_inventory_health_stats(self):
        """
        Calculate inventory health metrics across all active products:
        - Healthy: quantity > reorder_level
        - Low stock: 0 < quantity <= reorder_level
        - Out of stock: quantity == 0
        """
        products = self.get_all_products(include_archived=False)
        total_active = len(products)
        if total_active == 0:
            return {
                'total_active': 0,
                'healthy_count': 0,
                'low_stock_count': 0,
                'out_of_stock_count': 0,
                'health_percent': None,
                'health_label': 'N/A',
                'attention_count': 0,
            }
        healthy_count = sum(1 for p in products if p.quantity > p.reorder_level)
        low_stock_count = sum(1 for p in products if 0 < p.quantity <= p.reorder_level)
        out_of_stock_count = sum(1 for p in products if p.quantity == 0)
        health_percent = int(round((healthy_count / total_active) * 100))
        return {
            'total_active': total_active,
            'healthy_count': healthy_count,
            'low_stock_count': low_stock_count,
            'out_of_stock_count': out_of_stock_count,
            'health_percent': health_percent,
            'health_label': f'{health_percent}%',
            'attention_count': low_stock_count + out_of_stock_count,
        }

    def get_daily_movement_stats(self, days=7):
        """
        Retrieve daily Stock In and Stock Out sums for the last N calendar days
        based on actual database transaction records.
        """
        conn = self.db.get_connection()
        try:
            from datetime import timedelta
            current_day = today()
            dates = [current_day - timedelta(days=i) for i in range(days - 1, -1, -1)]
            date_strings = [d.strftime('%Y-%m-%d') for d in dates]

            rows = conn.execute(
                '''SELECT substr(created_at, 1, 10) as txn_date,
                          transaction_type,
                          SUM(quantity) as total_qty
                   FROM stock_transactions
                   WHERE replace(substr(created_at, 1, 10), 'T', ' ') >= ?
                     AND replace(substr(created_at, 1, 10), 'T', ' ') <= ?
                     AND transaction_type IN ('STOCK_IN', 'STOCK_OUT')
                   GROUP BY substr(created_at, 1, 10), transaction_type''',
                (date_strings[0], date_strings[-1])
            ).fetchall()

            totals = {}
            for r in rows:
                key = (r['txn_date'], r['transaction_type'])
                totals[key] = r['total_qty']

            result = []
            for d in dates:
                d_str = d.strftime('%Y-%m-%d')
                stock_in = totals.get((d_str, 'STOCK_IN'), 0)
                stock_out = totals.get((d_str, 'STOCK_OUT'), 0)
                result.append({
                    'date': d_str,
                    'label': d.strftime('%d %b'),
                    'day_name': d.strftime('%a'),
                    'stock_in': int(stock_in or 0),
                    'stock_out': int(stock_out or 0),
                })
            max_movement = max(
                (max(item['stock_in'], item['stock_out']) for item in result),
                default=0,
            )
            for item in result:
                item['stock_in_percentage'] = (
                    round(item['stock_in'] / max_movement * 100, 2)
                    if max_movement else 0
                )
                item['stock_out_percentage'] = (
                    round(item['stock_out'] / max_movement * 100, 2)
                    if max_movement else 0
                )
            return {
                'days': result,
                'max_movement': max_movement,
                'has_movement': max_movement > 0,
            }
        finally:
            conn.close()

    # ========================================================================
    # CSV EXPORT (using standard python csv.writer for safe escaping)
    # ========================================================================

    def export_products_csv(self):
        """Generate CSV string of all products with safe RFC 4180 escaping."""
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        def safe_text(value):
            text = str(value)
            return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text
        writer.writerow([
            'Product ID', 'Product Code (SKU)', 'Name', 'Category', 'Price', 'Quantity',
            'Reorder Level', 'Status', 'Stock Status', 'Created', 'Updated'
        ])
        products = self.get_all_products(include_archived=True)
        for p in products:
            status = 'Active' if p.is_active else 'Archived'
            stock_status = p.get_stock_status().replace('_', ' ').title()
            writer.writerow([
                p.product_id, safe_text(p.sku), safe_text(p.name), safe_text(p.category), p.price, p.quantity,
                p.reorder_level, status, stock_status, p.created_at, p.updated_at
            ])
        return output.getvalue()

    def export_transactions_csv(self):
        """Generate CSV string of all transactions with safe RFC 4180 escaping."""
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        def safe_text(value):
            text = str(value)
            return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text
        writer.writerow([
            'Transaction ID', 'Date', 'Product', 'SKU', 'Type', 'Quantity',
            'Stock Before', 'Stock After', 'Reason'
        ])
        transactions = self.get_transactions()
        for t in transactions:
            writer.writerow([
                t.transaction_id, t.created_at, safe_text(t.product_name), safe_text(t.product_sku),
                t.transaction_type, t.quantity, t.stock_before, t.stock_after,
                safe_text(t.reason)
            ])
        return output.getvalue()

    # ========================================================================
    # INTERNAL HELPERS
    # ========================================================================

    def _get_sku_map(self):
        """Return dict of {SKU_UPPER: product_id} for duplicate checking."""
        conn = self.db.get_connection()
        try:
            rows = conn.execute(
                'SELECT product_id, sku FROM products'
            ).fetchall()
            return {row['sku'].upper(): row['product_id'] for row in rows}
        finally:
            conn.close()
