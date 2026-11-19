"""
Utility Module for Stockly
===========================
PROGRAMMING PARADIGM: Procedural Programming

This module contains standalone, reusable functions that perform validation,
calculation, formatting, and checking. Each function takes explicit inputs
and returns explicit outputs — no hidden state or side effects.
"""

import math

from models import Product


# ============================================================================
# PROCEDURAL: Product-data validation
# ============================================================================

def validate_product_data(data, existing_skus=None, current_product_id=None):
    """
    Procedural function: validate a dict of product form data.
    Returns a list of human-readable error strings (empty list = valid).

    Parameters
    ----------
    data : dict            – form fields (name, sku, category, price, quantity, reorder_level)
    existing_skus : dict   – {sku_upper: product_id} for duplicate checking
    current_product_id : int or None – set when editing so the product's own SKU is allowed
    """
    errors = []

    # --- Name ---
    name = (data.get('name') or '').strip()
    if not name:
        errors.append('Product name is required.')
    elif len(name) > 200:
        errors.append('Product name must be 200 characters or fewer.')

    # --- SKU ---
    sku = (data.get('sku') or '').strip()
    if not sku:
        errors.append('SKU is required.')
    elif len(sku) > 50:
        errors.append('SKU must be 50 characters or fewer.')
    elif existing_skus is not None:
        owner_id = existing_skus.get(sku.upper())
        if owner_id is not None and owner_id != current_product_id:
            errors.append(f'SKU "{sku}" is already in use by another product.')

    # --- Category ---
    category = (data.get('category') or '').strip()
    if category not in Product.CATEGORIES:
        errors.append(f'Invalid category. Choose from: {", ".join(Product.CATEGORIES)}.')

    # --- Price ---
    try:
        price = float(data.get('price', ''))
        if not math.isfinite(price):
            errors.append('Unit price must be a finite number.')
        elif price < 0:
            errors.append('Unit price cannot be negative.')
    except (ValueError, TypeError):
        errors.append('Unit price must be a valid number.')

    # --- Quantity (only validated when adding a new product) ---
    if current_product_id is None:
        try:
            quantity = int(data.get('quantity', 0))
            if quantity < 0:
                errors.append('Opening quantity cannot be negative.')
        except (ValueError, TypeError):
            errors.append('Quantity must be a valid whole number.')

    # --- Reorder Level ---
    try:
        reorder_level = int(data.get('reorder_level', 0))
        if reorder_level < 0:
            errors.append('Reorder level cannot be negative.')
    except (ValueError, TypeError):
        errors.append('Reorder level must be a valid whole number.')

    return errors


# ============================================================================
# PROCEDURAL: Stock-movement validation
# ============================================================================

def validate_stock_movement(product, quantity_str, movement_type):
    """
    Validate a stock-in or stock-out request.
    Returns (quantity: int, errors: list[str]).
    """
    errors = []

    if product is None:
        errors.append('Product not found.')
        return 0, errors

    if not product.is_active:
        errors.append('Cannot perform stock operations on an archived product.')
        return 0, errors

    # Quantity
    try:
        quantity = int(quantity_str)
    except (ValueError, TypeError):
        errors.append('Quantity must be a valid whole number.')
        return 0, errors

    if quantity <= 0:
        errors.append('Quantity must be a positive number.')
        return 0, errors

    # Stock-out specific
    if movement_type == 'STOCK_OUT' and quantity > product.quantity:
        errors.append(
            f'Insufficient stock. Available: {product.quantity}, '
            f'Requested: {quantity}.'
        )

    return quantity, errors


# ============================================================================
# PROCEDURAL: Inventory calculations
# ============================================================================

def calculate_inventory_value(products):
    """
    Procedural function: compute total inventory value from a list of Products.
    Total = Σ (unit_price × quantity) for each active product.
    """
    return round(sum(p.price * p.quantity for p in products if p.is_active), 2)


def calculate_total_stock_units(products):
    """Sum of quantity across all active products."""
    return sum(p.quantity for p in products if p.is_active)


# ============================================================================
# PROCEDURAL: Stock-status checking
# ============================================================================

def check_low_stock(product):
    """Return True if the product is at or below its reorder level and active."""
    return (product.is_active
            and product.quantity <= product.reorder_level
            and product.quantity > 0)


def check_out_of_stock(product):
    """Return True if the product is active and has zero quantity."""
    return product.is_active and product.quantity == 0


def count_low_stock_products(products):
    """Count how many active products are at or below their reorder level (but >0)."""
    return sum(1 for p in products if check_low_stock(p))


# ============================================================================
# PROCEDURAL: Formatting helpers
# ============================================================================

def format_currency(value):
    """Format a number as Indian Rupees with comma grouping."""
    try:
        value = float(value)
    except (ValueError, TypeError):
        return '₹0.00'
    # Indian-style comma grouping is complex; use simple thousands separator
    if value < 0:
        return f'-₹{abs(value):,.2f}'
    return f'₹{value:,.2f}'


def format_datetime(dt_string):
    """
    Format an ISO / SQLite datetime string into a human-friendly form.
    '2026-11-19 14:30:00' → '19 Nov 2026, 02:30 PM'
    """
    if not dt_string:
        return ''
    from datetime import datetime
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
        try:
            dt = datetime.strptime(dt_string, fmt)
            return dt.strftime('%d %b %Y, %I:%M %p')
        except ValueError:
            continue
    return dt_string  # Return as-is if parsing fails


def format_stock_status(status):
    """Convert internal status key or transaction type to display label."""
    mapping = {
        'in_stock': 'In Stock',
        'low_stock': 'Low Stock',
        'out_of_stock': 'Out of Stock',
        'STOCK_IN': 'Stock In',
        'STOCK_OUT': 'Stock Out',
        'OPENING': 'Opening Stock',
    }
    return mapping.get(status, str(status).replace('_', ' ').title())


# ============================================================================
# PROCEDURAL: SKU generation helper
# ============================================================================

def generate_sku_suggestion(name, category):
    """
    Generate a SKU suggestion from the product name and category.
    Example: 'Wireless Mouse', 'Electronics' → 'ELE-WIRELES'
    """
    cat_prefix = (category or 'OTH')[:3].upper()
    name_part = ''.join(c for c in (name or '') if c.isalnum()).upper()[:7]
    if not name_part:
        name_part = 'PROD'
    return f'{cat_prefix}-{name_part}'
