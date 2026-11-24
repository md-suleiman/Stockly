"""
Models Module for Stockly
==========================
PROGRAMMING PARADIGM: Object-Oriented Programming (OOP)

This module defines domain-entity classes (Product, StockTransaction) that
encapsulate data attributes and business-logic methods. Factory class-methods
convert raw database rows into rich objects.
"""

from clock import timestamp


class Product:
    """
    OOP Concepts demonstrated:
      - Encapsulation: attributes are grouped inside the class.
      - Class Method (Factory Pattern): from_row() builds instances from DB rows.
      - Instance Methods: get_stock_status(), get_inventory_value().
      - Class-level Constants: CATEGORIES shared by all instances.
    """

    CATEGORIES = [
        'Electronics', 'Grocery', 'Stationery',
        'Clothing', 'Home & Living', 'Other'
    ]

    def __init__(self, product_id=None, sku='', name='', category='Other',
                 price=0.0, quantity=0, reorder_level=0, is_active=1,
                 created_at=None, updated_at=None):
        self.product_id = product_id
        self.sku = sku
        self.name = name
        self.category = category
        self.price = float(price)
        self.quantity = int(quantity)
        self.reorder_level = int(reorder_level)
        self.is_active = int(is_active)
        self.created_at = created_at or timestamp()
        self.updated_at = updated_at or timestamp()

    # -- OOP: Class Method / Factory Pattern ---------------------------------
    @classmethod
    def from_row(cls, row):
        """Create a Product from a database row; returns None for a None row."""
        if row is None:
            return None
        return cls(
            product_id=row['product_id'],
            sku=row['sku'],
            name=row['name'],
            category=row['category'],
            price=row['price'],
            quantity=row['quantity'],
            reorder_level=row['reorder_level'],
            is_active=row['is_active'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )

    @property
    def unit_price(self):
        """Alias for price to support varied template and API naming conventions."""
        return self.price

    # -- OOP: Instance method with business logic ----------------------------
    def get_stock_status(self):
        """Return a human-readable stock-status string."""
        if self.quantity == 0:
            return 'out_of_stock'
        elif self.quantity <= self.reorder_level:
            return 'low_stock'
        return 'in_stock'

    def get_inventory_value(self):
        """unit_price × current_quantity."""
        return round(self.price * self.quantity, 2)

    def to_dict(self):
        """Serialize the product for JSON / template consumption."""
        return {
            'product_id': self.product_id,
            'sku': self.sku,
            'name': self.name,
            'category': self.category,
            'price': self.price,
            'unit_price': self.price,
            'quantity': self.quantity,
            'reorder_level': self.reorder_level,
            'is_active': self.is_active,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'stock_status': self.get_stock_status(),
            'inventory_value': self.get_inventory_value(),
        }

    def __repr__(self):
        return (f"Product(id={self.product_id}, sku='{self.sku}', "
                f"name='{self.name}', qty={self.quantity})")


class StockTransaction:
    """
    OOP Concepts demonstrated:
      - Encapsulation of transaction data.
      - Factory class-method from_row().
      - Class-level constant TYPES for allowed transaction types.
    """

    TYPES = ['STOCK_IN', 'STOCK_OUT', 'OPENING']

    def __init__(self, transaction_id=None, product_id=None,
                 transaction_type='', quantity=0, stock_before=0,
                 stock_after=0, reason='', created_at=None,
                 product_name=None, product_sku=None):
        self.transaction_id = transaction_id
        self.product_id = product_id
        self.transaction_type = transaction_type
        self.quantity = int(quantity)
        self.stock_before = int(stock_before)
        self.stock_after = int(stock_after)
        self.reason = reason or ''
        self.created_at = created_at or timestamp()
        # Joined fields (populated when fetching with product info)
        self.product_name = product_name or ''
        self.product_sku = product_sku or ''

    @classmethod
    def from_row(cls, row):
        """Create a StockTransaction from a database row."""
        if row is None:
            return None
        keys = row.keys()
        return cls(
            transaction_id=row['transaction_id'],
            product_id=row['product_id'],
            transaction_type=row['transaction_type'],
            quantity=row['quantity'],
            stock_before=row['stock_before'],
            stock_after=row['stock_after'],
            reason=row['reason'],
            created_at=row['created_at'],
            product_name=row['name'] if 'name' in keys else '',
            product_sku=row['sku'] if 'sku' in keys else '',
        )

    def to_dict(self):
        return {
            'transaction_id': self.transaction_id,
            'product_id': self.product_id,
            'transaction_type': self.transaction_type,
            'quantity': self.quantity,
            'stock_before': self.stock_before,
            'stock_after': self.stock_after,
            'reason': self.reason,
            'created_at': self.created_at,
            'product_name': self.product_name,
            'product_sku': self.product_sku,
        }

    def __repr__(self):
        return (f"StockTransaction(id={self.transaction_id}, "
                f"type='{self.transaction_type}', qty={self.quantity})")
