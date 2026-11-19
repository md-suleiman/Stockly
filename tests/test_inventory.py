"""
Comprehensive Test Suite for Stockly
======================================
Tests all business logic, validation rules, database persistence,
and Flask HTTP endpoints.

Run using:
    python -m unittest tests/test_inventory.py -v
"""

import os
import tempfile
import unittest
import sqlite3
from datetime import date, timedelta
import app as app_module

from database import Database
from models import Product, StockTransaction
from inventory_service import InventoryService
from utils import (
    validate_product_data,
    validate_stock_movement,
    calculate_inventory_value,
    calculate_total_stock_units,
    check_low_stock,
    check_out_of_stock,
    format_currency,
    format_datetime
)
from seed import seed_database


class TestStocklyService(unittest.TestCase):
    """Unit tests for InventoryService and business logic using an isolated SQLite DB."""

    def setUp(self):
        """Create a fresh temporary SQLite database before every test."""
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        self.db = Database(db_path=self.temp_db_path)
        self.db.init_db()
        self.service = InventoryService(db=self.db)

    def tearDown(self):
        """Clean up and close temporary database file."""
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            try:
                os.unlink(self.temp_db_path)
            except PermissionError:
                pass

    def _sample_product_data(self, **overrides):
        data = {
            'name': 'Wireless Optical Mouse',
            'sku': 'ELE-WMOUSE-01',
            'category': 'Electronics',
            'price': '599.00',
            'quantity': '25',
            'reorder_level': '5',
        }
        data.update(overrides)
        return data

    # ------------------------------------------------------------------------
    # 1. Add valid product
    # ------------------------------------------------------------------------
    def test_add_valid_product(self):
        data = self._sample_product_data()
        product_id, errors = self.service.add_product(data)

        self.assertEqual(errors, [])
        self.assertIsNotNone(product_id)
        self.assertGreater(product_id, 0)

        # Retrieve and verify fields
        product = self.service.get_product(product_id)
        self.assertIsNotNone(product)
        self.assertEqual(product.name, 'Wireless Optical Mouse')
        self.assertEqual(product.sku, 'ELE-WMOUSE-01')
        self.assertEqual(product.category, 'Electronics')
        self.assertEqual(product.price, 599.00)
        self.assertEqual(product.quantity, 25)
        self.assertEqual(product.reorder_level, 5)
        self.assertEqual(product.is_active, 1)

    # ------------------------------------------------------------------------
    # 2. Reject empty product name
    # ------------------------------------------------------------------------
    def test_reject_empty_product_name(self):
        data = self._sample_product_data(name='   ')
        product_id, errors = self.service.add_product(data)

        self.assertIsNone(product_id)
        self.assertTrue(any('name is required' in e.lower() for e in errors))

    # ------------------------------------------------------------------------
    # 3. Reject duplicate SKU
    # ------------------------------------------------------------------------
    def test_reject_duplicate_sku(self):
        data1 = self._sample_product_data(sku='SKU-UNIQUE-101')
        prod_id1, errors1 = self.service.add_product(data1)
        self.assertIsNotNone(prod_id1)
        self.assertEqual(errors1, [])

        data2 = self._sample_product_data(name='Second Product', sku='SKU-UNIQUE-101')
        prod_id2, errors2 = self.service.add_product(data2)
        self.assertIsNone(prod_id2)
        self.assertTrue(any('already in use' in e.lower() for e in errors2))

    # ------------------------------------------------------------------------
    # 4. Reject negative price
    # ------------------------------------------------------------------------
    def test_reject_negative_price(self):
        data = self._sample_product_data(price='-150.00')
        product_id, errors = self.service.add_product(data)

        self.assertIsNone(product_id)
        self.assertTrue(any('negative' in e.lower() for e in errors))

    # ------------------------------------------------------------------------
    # 5. Edit product details (preserves stock quantity)
    # ------------------------------------------------------------------------
    def test_edit_product_details(self):
        data = self._sample_product_data(quantity='30')
        product_id, _ = self.service.add_product(data)

        update_data = {
            'name': 'Wireless Ergonomic Mouse Pro',
            'sku': 'ELE-WMOUSE-01',  # same SKU is allowed for same product
            'category': 'Electronics',
            'price': '799.00',
            'reorder_level': '8',
        }
        success, errors = self.service.update_product(product_id, update_data)
        self.assertTrue(success)
        self.assertEqual(errors, [])

        updated = self.service.get_product(product_id)
        self.assertEqual(updated.name, 'Wireless Ergonomic Mouse Pro')
        self.assertEqual(updated.price, 799.00)
        self.assertEqual(updated.reorder_level, 8)
        self.assertEqual(updated.quantity, 30)  # Quantity must remain unchanged

    # ------------------------------------------------------------------------
    # 6. Archive a product (soft delete preserving history)
    # ------------------------------------------------------------------------
    def test_archive_product(self):
        product_id, _ = self.service.add_product(self._sample_product_data())
        success, err = self.service.archive_product(product_id)
        self.assertTrue(success)
        self.assertIsNone(err)

        archived = self.service.get_product(product_id)
        self.assertEqual(archived.is_active, 0)

        # Active products listing should exclude it
        active_list = self.service.get_all_products(include_archived=False)
        self.assertFalse(any(p.product_id == product_id for p in active_list))

        # Include archived listing should include it
        all_list = self.service.get_all_products(include_archived=True)
        self.assertTrue(any(p.product_id == product_id for p in all_list))

    # ------------------------------------------------------------------------
    # 7. Search for products
    # ------------------------------------------------------------------------
    def test_search_for_product(self):
        self.service.add_product(self._sample_product_data(name='Red Ballpoint Pen', sku='STA-RPEN-01', category='Stationery'))
        self.service.add_product(self._sample_product_data(name='Blue Gel Pen', sku='STA-BPEN-02', category='Stationery'))
        self.service.add_product(self._sample_product_data(name='USB Hub 4-Port', sku='ELE-USBHUB', category='Electronics'))

        results = self.service.search_products(query='pen')
        self.assertEqual(len(results), 2)
        for p in results:
            self.assertIn('pen', p.name.lower())

        cat_results = self.service.search_products(category='Electronics')
        self.assertEqual(len(cat_results), 1)
        self.assertEqual(cat_results[0].sku, 'ELE-USBHUB')

    # ------------------------------------------------------------------------
    # 8. Perform valid Stock In
    # ------------------------------------------------------------------------
    def test_valid_stock_in(self):
        product_id, _ = self.service.add_product(self._sample_product_data(quantity='10'))

        success, message, new_qty = self.service.stock_in(product_id, '15', 'New shipment received')
        self.assertTrue(success)
        self.assertEqual(new_qty, 25)

        product = self.service.get_product(product_id)
        self.assertEqual(product.quantity, 25)

        # Check transaction logged
        txns = self.service.get_transactions(product_id=product_id, transaction_type='STOCK_IN')
        self.assertEqual(len(txns), 1)
        self.assertEqual(txns[0].quantity, 15)
        self.assertEqual(txns[0].stock_before, 10)
        self.assertEqual(txns[0].stock_after, 25)
        self.assertEqual(txns[0].reason, 'New shipment received')

    # ------------------------------------------------------------------------
    # 9. Perform valid Stock Out
    # ------------------------------------------------------------------------
    def test_valid_stock_out(self):
        product_id, _ = self.service.add_product(self._sample_product_data(quantity='20'))

        success, message, new_qty = self.service.stock_out(product_id, '8', 'Sold to retail customer')
        self.assertTrue(success)
        self.assertEqual(new_qty, 12)

        product = self.service.get_product(product_id)
        self.assertEqual(product.quantity, 12)

        # Check transaction logged
        txns = self.service.get_transactions(product_id=product_id, transaction_type='STOCK_OUT')
        self.assertEqual(len(txns), 1)
        self.assertEqual(txns[0].quantity, 8)
        self.assertEqual(txns[0].stock_before, 20)
        self.assertEqual(txns[0].stock_after, 12)

    # ------------------------------------------------------------------------
    # 10. Reject Stock Out exceeding available stock
    # ------------------------------------------------------------------------
    def test_reject_stock_out_exceeding_stock(self):
        product_id, _ = self.service.add_product(self._sample_product_data(quantity='5'))

        success, message, new_qty = self.service.stock_out(product_id, '10', 'Attempt to oversell')
        self.assertFalse(success)
        self.assertIsNone(new_qty)
        self.assertIn('insufficient stock', message.lower())

        # Quantity must remain intact
        product = self.service.get_product(product_id)
        self.assertEqual(product.quantity, 5)

        # No stock out transaction should be committed
        txns = self.service.get_transactions(product_id=product_id, transaction_type='STOCK_OUT')
        self.assertEqual(len(txns), 0)

    # ------------------------------------------------------------------------
    # 11. Reject zero or negative stock movement quantity
    # ------------------------------------------------------------------------
    def test_reject_zero_or_negative_stock_movement(self):
        product_id, _ = self.service.add_product(self._sample_product_data(quantity='10'))

        # Zero quantity
        success_in_zero, msg_zero, _ = self.service.stock_in(product_id, '0', 'zero in')
        self.assertFalse(success_in_zero)
        self.assertIn('positive', msg_zero.lower())

        # Negative quantity
        success_out_neg, msg_neg, _ = self.service.stock_out(product_id, '-5', 'negative out')
        self.assertFalse(success_out_neg)
        self.assertIn('positive', msg_neg.lower())

        # Non-numeric quantity
        success_nan, msg_nan, _ = self.service.stock_in(product_id, 'abc', 'invalid')
        self.assertFalse(success_nan)
        self.assertIn('whole number', msg_nan.lower())

    # ------------------------------------------------------------------------
    # 12. Trigger low-stock condition
    # ------------------------------------------------------------------------
    def test_low_stock_condition(self):
        product_id, _ = self.service.add_product(self._sample_product_data(
            name='Thermal Paper Roll',
            sku='STA-TPROLL',
            quantity='15',
            reorder_level='10'
        ))

        # Initially 15 > 10, not low stock
        low_stock_init = self.service.get_low_stock_products()
        self.assertFalse(any(p.product_id == product_id for p in low_stock_init))

        # Issue 8 units -> stock is 7 <= 10 (low stock!)
        self.service.stock_out(product_id, '8', 'Office usage')
        low_stock_after = self.service.get_low_stock_products()
        self.assertTrue(any(p.product_id == product_id for p in low_stock_after))

    # ------------------------------------------------------------------------
    # 13. Inventory value calculation
    # ------------------------------------------------------------------------
    def test_inventory_value_calculation(self):
        # Product 1: 10 * 100.00 = 1000.00
        self.service.add_product(self._sample_product_data(sku='P1', price='100.00', quantity='10'))
        # Product 2: 5 * 250.50 = 1252.50
        self.service.add_product(self._sample_product_data(sku='P2', price='250.50', quantity='5'))

        stats = self.service.get_dashboard_stats()
        # 1000.00 + 1252.50 = 2252.50
        self.assertEqual(stats['total_value'], 2252.50)
        self.assertEqual(stats['total_stock'], 15)
        self.assertEqual(stats['total_products'], 2)

    # ------------------------------------------------------------------------
    # 14. Verify transaction records are created (including OPENING)
    # ------------------------------------------------------------------------
    def test_transaction_records_creation(self):
        # Opening stock > 0 creates an OPENING transaction
        product_id, _ = self.service.add_product(self._sample_product_data(sku='TXN-TEST', quantity='12'))
        all_txns = self.service.get_transactions(product_id=product_id)
        self.assertEqual(len(all_txns), 1)
        self.assertEqual(all_txns[0].transaction_type, 'OPENING')
        self.assertEqual(all_txns[0].quantity, 12)
        self.assertEqual(all_txns[0].stock_before, 0)
        self.assertEqual(all_txns[0].stock_after, 12)

        # Subsequent movements
        self.service.stock_in(product_id, '4', 'Restock')
        self.service.stock_out(product_id, '2', 'Order')

        updated_txns = self.service.get_transactions(product_id=product_id)
        self.assertEqual(len(updated_txns), 3)

    # ------------------------------------------------------------------------
    # 15. Verify database persistence after reopening a connection
    # ------------------------------------------------------------------------
    def test_database_persistence_across_connections(self):
        product_id, _ = self.service.add_product(self._sample_product_data(sku='PERSIST-01', name='Persistent Item'))

        # Create completely new Database and Service pointing to the same file
        new_db = Database(db_path=self.temp_db_path)
        new_service = InventoryService(db=new_db)

        persisted_prod = new_service.get_product(product_id)
        self.assertIsNotNone(persisted_prod)
        self.assertEqual(persisted_prod.name, 'Persistent Item')
        self.assertEqual(persisted_prod.sku, 'PERSIST-01')

    # ------------------------------------------------------------------------
    # 16. Reject negative opening quantity and reorder level
    # ------------------------------------------------------------------------
    def test_reject_negative_quantity_and_reorder_level(self):
        data_neg_qty = self._sample_product_data(quantity='-10')
        _, errors_qty = self.service.add_product(data_neg_qty)
        self.assertTrue(any('negative' in e.lower() for e in errors_qty))

        data_neg_reorder = self._sample_product_data(reorder_level='-3')
        _, errors_reorder = self.service.add_product(data_neg_reorder)
        self.assertTrue(any('negative' in e.lower() for e in errors_reorder))

    # ------------------------------------------------------------------------
    # 17. Stock movement on archived product is prohibited
    # ------------------------------------------------------------------------
    def test_reject_stock_movement_on_archived_product(self):
        product_id, _ = self.service.add_product(self._sample_product_data(quantity='10'))
        self.service.archive_product(product_id)

        success_in, msg_in, _ = self.service.stock_in(product_id, '5', 'restock archived')
        self.assertFalse(success_in)
        self.assertIn('archived', msg_in.lower())

        success_out, msg_out, _ = self.service.stock_out(product_id, '2', 'sale archived')
        self.assertFalse(success_out)
        self.assertIn('archived', msg_out.lower())

    # ------------------------------------------------------------------------
    # 18. Procedural utilities test
    # ------------------------------------------------------------------------
    def test_procedural_utilities(self):
        self.assertEqual(format_currency(1234.5), '₹1,234.50')
        self.assertEqual(format_currency(123456.78), '₹1,23,456.78')
        self.assertEqual(format_currency(-123456.78), '-₹1,23,456.78')
        self.assertEqual(format_currency(0), '₹0.00')

        formatted_date = format_datetime('2026-11-19 14:30:00')
        self.assertIn('19 Nov 2026', formatted_date)

    # ------------------------------------------------------------------------
    # 19. Inventory Health Calculation
    # ------------------------------------------------------------------------
    def test_inventory_health_stats(self):
        # Product 1: healthy (qty 20 > reorder 5)
        self.service.add_product(self._sample_product_data(sku='H1', quantity='20', reorder_level='5'))
        # Product 2: low stock (qty 3 <= reorder 5)
        self.service.add_product(self._sample_product_data(sku='L1', quantity='3', reorder_level='5'))
        # Product 3: out of stock (qty 0)
        self.service.add_product(self._sample_product_data(sku='O1', quantity='0', reorder_level='5'))

        health = self.service.get_inventory_health_stats()
        self.assertEqual(health['total_active'], 3)
        self.assertEqual(health['healthy_count'], 1)
        self.assertEqual(health['low_stock_count'], 1)
        self.assertEqual(health['out_of_stock_count'], 1)
        self.assertEqual(health['attention_count'], 2)
        # 1 / 3 = 33%
        self.assertEqual(health['health_percent'], 33)

    def test_empty_inventory_health_is_not_healthy(self):
        health = self.service.get_inventory_health_stats()
        self.assertEqual(health['total_active'], 0)
        self.assertIsNone(health['health_percent'])
        self.assertEqual(health['health_label'], 'N/A')

    # ------------------------------------------------------------------------
    # 20. Daily Movement 7-Day Statistics
    # ------------------------------------------------------------------------
    def test_daily_movement_stats(self):
        p_id, _ = self.service.add_product(self._sample_product_data(sku='DM-1', quantity='10'))
        self.service.stock_in(p_id, '5', 'Batch restock')
        self.service.stock_out(p_id, '2', 'Order')

        movements = self.service.get_daily_movement_stats(days=7)
        self.assertEqual(len(movements['days']), 7)
        self.assertTrue(movements['has_movement'])
        self.assertEqual(movements['max_movement'], 5)
        # Opening balances are not ordinary Stock In movement.
        today_data = movements['days'][-1]
        self.assertEqual(today_data['stock_in'], 5)
        self.assertGreaterEqual(today_data['stock_out'], 2)

    def test_daily_movement_empty_state_and_percentages(self):
        empty = self.service.get_daily_movement_stats(days=7)
        self.assertEqual(len(empty['days']), 7)
        self.assertFalse(empty['has_movement'])
        self.assertTrue(all(d['stock_in_percentage'] == 0 for d in empty['days']))

        product_id, _ = self.service.add_product(self._sample_product_data(
            sku='SCALE-1', quantity='1'
        ))
        self.service.stock_in(product_id, '99', 'Large receipt')
        movement = self.service.get_daily_movement_stats(days=7)
        self.assertEqual(movement['max_movement'], 99)
        self.assertEqual(movement['days'][-1]['stock_in_percentage'], 100)

    # ------------------------------------------------------------------------
    # 21. CSV Export RFC4180 Escaping (handles quotes and commas safely)
    # ------------------------------------------------------------------------
    def test_csv_export_rfc4180_escaping(self):
        self.service.add_product(self._sample_product_data(
            name='Cable, HDMI "High-Speed", 2m',
            sku='CBL-HDMI-2M'
        ))
        csv_text = self.service.export_products_csv()
        import csv
        import io
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        # Verify header + at least 1 product row
        self.assertGreaterEqual(len(rows), 2)
        # Name should be read intact with commas and quotes
        names = [r[2] for r in rows[1:]]
        self.assertIn('Cable, HDMI "High-Speed", 2m', names)


class TestStocklyFlaskRoutes(unittest.TestCase):
    """Integration tests for Flask HTTP routing using the Flask test client."""

    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        self.route_db = Database(db_path=self.temp_db_path)
        self.route_db.init_db()
        self.route_service = InventoryService(db=self.route_db)
        self.test_app = app_module.create_app(self.route_service)
        self.test_app.config['TESTING'] = True
        self.test_app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.test_app.test_client()

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.unlink(self.temp_db_path)

    def test_dashboard_route(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Resource Management', response.data)
        self.assertIn(b'Your inventory at a glance.', response.data)

    def test_products_route(self):
        response = self.client.get('/products')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Products', response.data)

    def test_stock_route(self):
        response = self.client.get('/stock')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Stock Management', response.data)

    def test_transactions_route(self):
        response = self.client.get('/transactions')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Transaction History', response.data)

    def test_reports_route(self):
        response = self.client.get('/reports')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Reports', response.data)

    def test_settings_route(self):
        response = self.client.get('/settings')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Settings', response.data)

    def test_route_breadcrumbs_are_contextual(self):
        response = self.client.get('/products')
        self.assertIn(b'Stockly', response.data)
        self.assertIn(b'Inventory', response.data)
        self.assertIn(b'Products', response.data)
        self.assertNotIn(b'Warehouse Console', response.data)
        self.assertNotIn(b'Quick Actions', response.data)
        self.assertNotIn(b'quick-actions', response.data)

    def test_restock_query_preselects_product_in_stock_in_mode(self):
        product_id, errors = self.route_service.add_product(
            self._route_product_data(sku='RESTOCK-1')
        )
        self.assertEqual(errors, [])
        response = self.client.get(f'/stock?mode=in&product_id={product_id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(f'value="{product_id}" selected'.encode(), response.data)

    def test_non_finite_price_is_rejected(self):
        _, errors = self.route_service.add_product(
            self._route_product_data(sku='NAN-PRICE', price='NaN')
        )
        self.assertTrue(any('finite' in error for error in errors))

    def test_restore_product_route(self):
        product_id, errors = self.route_service.add_product(
            self._route_product_data(sku='RESTORE-1')
        )
        self.assertEqual(errors, [])
        self.route_service.archive_product(product_id)
        response = self.client.post(f'/products/restore/{product_id}')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.route_service.get_product(product_id).is_active)

    def test_csv_formula_text_is_prefixed(self):
        self.route_service.add_product(self._route_product_data(
            name='=2+2', sku='@FORMULA-1'
        ))
        csv_text = self.route_service.export_products_csv()
        self.assertIn("'=2+2", csv_text)
        self.assertIn("'@FORMULA-1", csv_text)

    def test_csv_export_routes(self):
        res_prod = self.client.get('/reports/export/products')
        self.assertEqual(res_prod.status_code, 200)
        self.assertEqual(res_prod.mimetype, 'text/csv')

        res_txn = self.client.get('/reports/export/transactions')
        self.assertEqual(res_txn.status_code, 200)
        self.assertEqual(res_txn.mimetype, 'text/csv')


    def test_stock_in_invalid_product_id(self):
        res = self.client.post('/stock/in', data={'product_id': 'invalid', 'quantity': '5'})
        self.assertEqual(res.status_code, 302)
        follow_up = self.client.get(res.headers['Location'])
        self.assertEqual(follow_up.status_code, 200)
        self.assertIn(b'Please select a valid product', follow_up.data)

    def test_stock_out_invalid_product_id(self):
        res = self.client.post('/stock/out', data={'product_id': '-1', 'quantity': '5'})
        self.assertEqual(res.status_code, 302)
        follow_up = self.client.get(res.headers['Location'])
        self.assertIn(b'Please select a valid product', follow_up.data)

    def test_successful_stock_post_uses_prg_without_duplicate_on_refresh(self):
        product_id, errors = self.route_service.add_product(
            self._route_product_data(quantity='0')
        )
        self.assertEqual(errors, [])
        response = self.client.post(
            '/stock/in',
            data={'product_id': str(product_id), 'quantity': '4', 'reason': 'delivery'},
        )
        self.assertEqual(response.status_code, 302)
        location = response.headers['Location']
        self.client.get(location)
        self.client.get(location)
        transactions = self.route_service.get_transactions(product_id=product_id)
        self.assertEqual(len([t for t in transactions if t.transaction_type == 'STOCK_IN']), 1)
        self.assertEqual(self.route_service.get_product(product_id).quantity, 4)

    def test_error_pages_return_http_errors(self):
        self.assertEqual(self.client.get('/missing-page').status_code, 404)
        self.test_app.config['TESTING'] = False
        self.test_app.view_functions['stockly.dashboard'] = lambda: (_ for _ in ()).throw(
            RuntimeError('test failure')
        )
        response = self.client.get('/')
        self.assertEqual(response.status_code, 500)
        self.assertIn(b'Something went wrong', response.data)

    def test_factory_instances_have_isolated_services(self):
        other_fd, other_path = tempfile.mkstemp(suffix='.db')
        os.close(other_fd)
        try:
            other_db = Database(db_path=other_path)
            other_db.init_db()
            other_service = InventoryService(db=other_db)
            other_app = app_module.create_app(other_service)
            product_id, _ = self.route_service.add_product(
                self._route_product_data(sku='ISOLATED-1')
            )
            self.assertIsNone(other_service.get_product(product_id))
            self.assertEqual(other_app.test_client().get('/products').status_code, 200)
        finally:
            os.unlink(other_path)

    def _route_product_data(self, **overrides):
        data = {
            'name': 'Route Test Product',
            'sku': 'ROUTE-TEST-1',
            'category': 'Electronics',
            'price': '10',
            'quantity': '1',
            'reorder_level': '1',
        }
        data.update(overrides)
        return data


class TestHistoricalSeed(unittest.TestCase):
    def test_seed_is_historical_consistent_and_idempotent(self):
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            first = seed_database(path)
            second = seed_database(path)
            self.assertEqual(first['products_added'], 9)
            self.assertEqual(first['transactions_added'], 34)
            self.assertEqual(second['transactions_added'], 0)
            conn = sqlite3.connect(path)
            self.assertEqual(conn.execute(
                "SELECT COUNT(DISTINCT substr(created_at, 1, 10)) "
                "FROM stock_transactions WHERE reason NOT LIKE '[DEMO]%' "
                "AND transaction_type IN ('STOCK_IN', 'STOCK_OUT')"
            ).fetchone()[0], 7)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM stock_transactions WHERE stock_after < 0"
            ).fetchone()[0], 0)
            conn.close()
        finally:
            os.unlink(path)

    def test_seed_preserves_legacy_zero_stock_products_and_v1_marker(self):
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            db = Database(path)
            db.init_db()
            conn = db.get_connection()
            conn.execute(
                '''INSERT INTO products
                   (sku, name, category, price, quantity, reorder_level,
                    is_active, created_at, updated_at)
                   VALUES ('ELE-WMOUSE', 'Legacy Mouse', 'Electronics',
                           10, 0, 1, 1, '2026-11-19 08:00:00',
                           '2026-11-19 08:00:00')'''
            )
            conn.execute(
                "INSERT INTO app_metadata(key, value) VALUES ('demo_seed', 'historical-demo-v1')"
            )
            conn.commit()
            conn.close()
            result = seed_database(path)
            self.assertEqual(result['products_added'], 9)
            conn = sqlite3.connect(path)
            self.assertEqual(conn.execute(
                "SELECT name FROM products WHERE sku = 'ELE-WMOUSE'"
            ).fetchone()[0], 'Legacy Mouse')
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM products WHERE sku IN "
                "('ELE-MOU-014', 'ELE-CAB-021', 'ELE-KEY-009', 'STA-NOT-008', "
                "'HOM-WAT-006', 'CLO-BAG-011', 'GRO-RIC-003', 'ELE-SPK-017', "
                "'STA-PAP-012')"
            ).fetchone()[0], 9)
            conn.close()
        finally:
            os.unlink(path)

    def test_seed_populates_every_day_with_both_movement_types_and_varied_quantities(self):
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            seed_database(path)
            conn = sqlite3.connect(path)
            rows = conn.execute(
                """SELECT substr(created_at, 1, 10), transaction_type,
                          SUM(quantity)
                   FROM stock_transactions
                   WHERE reason NOT LIKE '[DEMO]%'
                     AND transaction_type IN ('STOCK_IN', 'STOCK_OUT')
                   GROUP BY 1, 2"""
            ).fetchall()
            by_day = {}
            for txn_date, txn_type, quantity in rows:
                by_day.setdefault(txn_date, {})[txn_type] = quantity
            self.assertEqual(set(by_day), {
                (date.today() - timedelta(days=i)).isoformat() for i in range(7)
            })
            self.assertTrue(all(
                set(day) == {'STOCK_IN', 'STOCK_OUT'} for day in by_day.values()
            ))
            self.assertGreater(len({
                tuple(day.values()) for day in by_day.values()
            }), 1)
            conn.close()
        finally:
            os.unlink(path)

    def test_transaction_date_filters_accept_space_and_iso_timestamps(self):
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = Database(path)
        db.init_db()
        service = InventoryService(db)
        product_id, errors = service.add_product({
            'name': 'Date Filter Product',
            'sku': 'DATE-FILTER-1',
            'category': 'Electronics',
            'price': '10',
            'quantity': '0',
            'reorder_level': '1',
        })
        self.assertEqual(errors, [])
        conn = db.get_connection()
        conn.execute(
            '''INSERT INTO stock_transactions
               (product_id, transaction_type, quantity, stock_before,
                stock_after, reason, created_at)
               VALUES (?, 'STOCK_IN', 2, 0, 2, 'iso', '2026-11-19T10:00:00')''',
            (product_id,),
        )
        conn.execute(
            '''INSERT INTO stock_transactions
               (product_id, transaction_type, quantity, stock_before,
                stock_after, reason, created_at)
               VALUES (?, 'STOCK_OUT', 1, 2, 1, 'space', '2026-11-19 12:00:00')''',
            (product_id,),
        )
        conn.commit()
        conn.close()
        transactions = service.get_transactions(
            product_id=product_id,
            date_from='2026-11-19',
            date_to='2026-11-19',
            sort_order='ASC',
        )
        self.assertEqual([txn.reason for txn in transactions], ['iso', 'space'])
        os.unlink(path)


if __name__ == '__main__':
    unittest.main()
