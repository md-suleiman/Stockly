"""
Seed Script for Stockly
========================
Populates the database with realistic demonstration data.
Safe to run more than once — checks for existing products by SKU
before inserting.

Usage:
    python seed.py
"""

from database import Database
from inventory_service import InventoryService
from datetime import datetime, timedelta
import random


def seed_database():
    """Insert sample products and transactions if the database is empty or missing them."""
    db = Database()
    db.init_db()
    service = InventoryService(db)

    # Check if data already exists
    existing = service.get_all_products(include_archived=True)
    existing_skus = {p.sku.upper() for p in existing}

    sample_products = [
        {
            'name': 'Wireless Mouse',
            'sku': 'ELE-WMOUSE',
            'category': 'Electronics',
            'price': '599.00',
            'quantity': '45',
            'reorder_level': '10',
        },
        {
            'name': 'USB-C Cable (1m)',
            'sku': 'ELE-USBC1M',
            'category': 'Electronics',
            'price': '199.00',
            'quantity': '120',
            'reorder_level': '20',
        },
        {
            'name': 'Laptop Stand',
            'sku': 'ELE-LPSTND',
            'category': 'Electronics',
            'price': '1499.00',
            'quantity': '8',
            'reorder_level': '5',
        },
        {
            'name': 'Spiral Notebook (200 pages)',
            'sku': 'STA-NB200',
            'category': 'Stationery',
            'price': '85.00',
            'quantity': '200',
            'reorder_level': '50',
        },
        {
            'name': 'Ballpoint Pen Pack (10)',
            'sku': 'STA-BPPEN10',
            'category': 'Stationery',
            'price': '120.00',
            'quantity': '5',           # Low stock
            'reorder_level': '15',
        },
        {
            'name': 'Stainless Steel Water Bottle',
            'sku': 'HOM-WTRBOTL',
            'category': 'Home & Living',
            'price': '450.00',
            'quantity': '0',           # Out of stock
            'reorder_level': '10',
        },
        {
            'name': 'Canvas Backpack',
            'sku': 'CLO-BKPACK',
            'category': 'Clothing',
            'price': '1299.00',
            'quantity': '25',
            'reorder_level': '8',
        },
        {
            'name': 'Over-Ear Headphones',
            'sku': 'ELE-HDPHN',
            'category': 'Electronics',
            'price': '2499.00',
            'quantity': '3',           # Low stock
            'reorder_level': '5',
        },
        {
            'name': 'Mechanical Keyboard',
            'sku': 'ELE-MCKBD',
            'category': 'Electronics',
            'price': '3499.00',
            'quantity': '15',
            'reorder_level': '5',
        },
        {
            'name': 'Basmati Rice (5 kg)',
            'sku': 'GRO-RICE5K',
            'category': 'Grocery',
            'price': '375.00',
            'quantity': '60',
            'reorder_level': '20',
        },
        {
            'name': 'Green Tea (25 bags)',
            'sku': 'GRO-GTEA25',
            'category': 'Grocery',
            'price': '150.00',
            'quantity': '0',           # Out of stock
            'reorder_level': '10',
        },
        {
            'name': 'Cotton T-Shirt (M)',
            'sku': 'CLO-TSHRTM',
            'category': 'Clothing',
            'price': '499.00',
            'quantity': '40',
            'reorder_level': '10',
        },
    ]

    added_ids = []
    for prod_data in sample_products:
        if prod_data['sku'].upper() in existing_skus:
            print(f"  ⏭  SKU {prod_data['sku']} already exists, skipping.")
            continue
        product_id, errors = service.add_product(prod_data)
        if errors:
            print(f"  ✗  Failed to add {prod_data['name']}: {errors}")
        else:
            print(f"  ✓  Added {prod_data['name']} (ID: {product_id})")
            added_ids.append(product_id)

    # Add some sample stock movements for newly added products
    if added_ids:
        print('\n  Adding sample stock transactions...')
        # Only add transactions for products we just created
        products = service.get_all_products(include_archived=False)
        new_products = [p for p in products if p.product_id in added_ids and p.quantity > 5]

        movements = [
            ('STOCK_IN', 'Supplier delivery'),
            ('STOCK_OUT', 'Customer order fulfilled'),
            ('STOCK_IN', 'Restocking from warehouse'),
            ('STOCK_OUT', 'Walk-in customer purchase'),
            ('STOCK_IN', 'Bulk purchase received'),
        ]

        for product in new_products[:5]:
            for move_type, reason in random.sample(movements, min(2, len(movements))):
                if move_type == 'STOCK_IN':
                    qty = str(random.randint(5, 20))
                    success, msg, _ = service.stock_in(product.product_id, qty, reason)
                else:
                    max_out = min(product.quantity, 10)
                    if max_out < 1:
                        continue
                    qty = str(random.randint(1, max_out))
                    success, msg, _ = service.stock_out(product.product_id, qty, reason)
                # Re-fetch to get updated quantity
                product = service.get_product(product.product_id)
                status = '✓' if success else '✗'
                print(f"    {status}  {move_type} {qty} × {product.name}: {msg}")

    print('\n  Seed complete!')


if __name__ == '__main__':
    print('=' * 60)
    print('  STOCKLY — Seeding Database')
    print('=' * 60)
    seed_database()

