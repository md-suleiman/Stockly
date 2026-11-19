"""
Inventory Service Module for Stockly
======================================
PROGRAMMING PARADIGM: Object-Oriented Programming (OOP)

The InventoryService class is the central business-logic layer. It mediates
between Flask routes and the SQLite database, performing validation, atomic
stock operations, and report generation. This follows the Service Pattern —
a common OOP architectural approach.
"""

from datetime import datetime
from database import Database
from models import Product, StockTransaction
from utils import validate_product_data, validate_stock_movement


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

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
        except Exception as e:
            conn.rollback()
            return None, [f'Database error: {str(e)}']
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

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
        except Exception as e:
            conn.rollback()
            return False, [f'Database error: {str(e)}']
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

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = self.db.get_connection()
        try:
            conn.execute(
                'UPDATE products SET is_active = 0, updated_at = ? '
                'WHERE product_id = ?',
                (now, product_id)
            )
            conn.commit()
            return True, None
        except Exception as e:
            conn.rollback()
            return False, f'Database error: {str(e)}'
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
        product = self.get_product(product_id)
        quantity, errors = validate_stock_movement(product, quantity_str, 'STOCK_IN')
        if errors:
            return False, errors[0], None

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        stock_before = product.quantity
        stock_after = stock_before + quantity

        conn = self.db.get_connection()
        try:
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
        except Exception as e:
            conn.rollback()
            return False, f'Database error: {str(e)}', None
        finally:
            conn.close()

    def stock_out(self, product_id, quantity_str, reason=''):
        """
        Decrease stock. Atomic: quantity update + transaction record in one commit.
        Returns (success, message, updated_quantity).
        """
        product = self.get_product(product_id)
        quantity, errors = validate_stock_movement(product, quantity_str, 'STOCK_OUT')
        if errors:
            return False, errors[0], None

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        stock_before = product.quantity
        stock_after = stock_before - quantity

        conn = self.db.get_connection()
        try:
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
        except Exception as e:
            conn.rollback()
            return False, f'Database error: {str(e)}', None
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
                sql += ' AND t.created_at >= ?'
                params.append(date_from)

            if date_to:
                sql += ' AND t.created_at <= ?'
                params.append(date_to + ' 23:59:59')

            if search:
                sql += ' AND (LOWER(p.name) LIKE ? OR LOWER(p.sku) LIKE ? OR LOWER(t.reason) LIKE ?)'
                q = f'%{search.lower()}%'
                params.extend([q, q, q])

            if str(sort_order).upper() in ('ASC', 'OLDEST'):
                sql += ' ORDER BY t.created_at ASC'
            else:
                sql += ' ORDER BY t.created_at DESC'

            rows = conn.execute(sql, params).fetchall()
            return [StockTransaction.from_row(r) for r in rows]
        finally:
            conn.close()

    # ========================================================================
    # DASHBOARD & REPORTS
    # ========================================================================

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
                   ORDER BY t.created_at DESC
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

    # ========================================================================
    # CSV EXPORT
    # ========================================================================

    def export_products_csv(self):
        """Generate CSV string of all products."""
        products = self.get_all_products(include_archived=True)
        lines = ['Product ID,SKU,Name,Category,Price,Quantity,Reorder Level,'
                 'Status,Stock Status,Created,Updated']
        for p in products:
            status = 'Active' if p.is_active else 'Archived'
            stock_status = p.get_stock_status().replace('_', ' ').title()
            lines.append(
                f'{p.product_id},"{p.sku}","{p.name}","{p.category}",'
                f'{p.price},{p.quantity},{p.reorder_level},'
                f'{status},{stock_status},"{p.created_at}","{p.updated_at}"'
            )
        return '\n'.join(lines)

    def export_transactions_csv(self):
        """Generate CSV string of all transactions."""
        transactions = self.get_transactions()
        lines = ['Transaction ID,Date,Product,SKU,Type,Quantity,'
                 'Stock Before,Stock After,Reason']
        for t in transactions:
            lines.append(
                f'{t.transaction_id},"{t.created_at}","{t.product_name}",'
                f'"{t.product_sku}",{t.transaction_type},{t.quantity},'
                f'{t.stock_before},{t.stock_after},"{t.reason}"'
            )
        return '\n'.join(lines)

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

