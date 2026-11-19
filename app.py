"""
Stockly — Flask Application
=============================
Main entry point. Defines all HTTP routes and connects the browser UI
to the InventoryService business-logic layer.

PROGRAMMING PARADIGM: Event-Driven (HTTP request → route handler → response)
Each Flask route is an event handler triggered by a browser request.
"""

from flask import (Flask, render_template, request, redirect,
                   url_for, flash, Response)
from inventory_service import InventoryService
from models import Product
from utils import format_currency, format_datetime, format_stock_status

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = 'stockly-secret-key-dev'

# Create the shared service instance
service = InventoryService()

# ---------------------------------------------------------------------------
# Jinja2 custom filters — available in every template
# ---------------------------------------------------------------------------
app.jinja_env.filters['currency'] = format_currency
app.jinja_env.filters['datefmt'] = format_datetime
app.jinja_env.filters['stockstatus'] = format_stock_status


# ============================================================================
# DASHBOARD
# ============================================================================

@app.route('/')
def dashboard():
    """
    Event-Driven: GET / triggers dashboard rendering.
    All KPI metrics are computed from the database.
    """
    stats = service.get_dashboard_stats()
    low_stock = service.get_low_stock_products()
    recent_txns = service.get_recent_transactions(limit=8)
    category_data = service.get_category_breakdown()
    return render_template('dashboard.html',
                           stats=stats,
                           low_stock_products=low_stock,
                           recent_transactions=recent_txns,
                           category_data=category_data)


# ============================================================================
# PRODUCTS
# ============================================================================

@app.route('/products')
def products():
    """List products with search, filter, sort."""
    search_query = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '')
    status_filter = request.args.get('status', '')
    sort_by = request.args.get('sort', 'created_at')
    include_archived = request.args.get('archived', '') == '1'

    product_list = service.search_products(
        query=search_query,
        category=category_filter,
        status=status_filter,
        sort_by=sort_by,
        include_archived=include_archived,
    )
    return render_template('products.html',
                           products=product_list,
                           categories=Product.CATEGORIES,
                           search_query=search_query,
                           category_filter=category_filter,
                           status_filter=status_filter,
                           sort_by=sort_by,
                           include_archived=include_archived)


@app.route('/products/add', methods=['GET', 'POST'])
def add_product():
    """Show the add-product form (GET) or process submission (POST)."""
    if request.method == 'POST':
        data = {
            'name': request.form.get('name', ''),
            'sku': request.form.get('sku', ''),
            'category': request.form.get('category', ''),
            'price': request.form.get('price') or request.form.get('unit_price', ''),
            'quantity': request.form.get('quantity', '0'),
            'reorder_level': request.form.get('reorder_level', '0'),
        }
        product_id, errors = service.add_product(data)
        if errors:
            return render_template('product_form.html',
                                   mode='add',
                                   product=data,
                                   categories=Product.CATEGORIES,
                                   errors=errors)
        flash('Product added successfully!', 'success')
        return redirect(url_for('products'))

    return render_template('product_form.html',
                           mode='add',
                           product={},
                           categories=Product.CATEGORIES,
                           errors=[])


@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    """Edit an existing product's details (not quantity)."""
    product = service.get_product(product_id)
    if product is None:
        flash('Product not found.', 'error')
        return redirect(url_for('products'))

    if request.method == 'POST':
        data = {
            'name': request.form.get('name', ''),
            'sku': request.form.get('sku', ''),
            'category': request.form.get('category', ''),
            'price': request.form.get('price') or request.form.get('unit_price', ''),
            'reorder_level': request.form.get('reorder_level', '0'),
        }
        success, errors = service.update_product(product_id, data)
        if not success:
            return render_template('product_form.html',
                                   mode='edit',
                                   product=data,
                                   product_id=product_id,
                                   categories=Product.CATEGORIES,
                                   errors=errors)
        flash('Product updated successfully!', 'success')
        return redirect(url_for('products'))

    return render_template('product_form.html',
                           mode='edit',
                           product=product.to_dict(),
                           product_id=product_id,
                           categories=Product.CATEGORIES,
                           errors=[])


@app.route('/products/archive/<int:product_id>', methods=['POST'])
def archive_product(product_id):
    """Archive (soft-delete) a product."""
    success, error = service.archive_product(product_id)
    if success:
        flash('Product archived successfully.', 'success')
    else:
        flash(error or 'Failed to archive product.', 'error')
    return redirect(url_for('products'))


# ============================================================================
# STOCK MANAGEMENT
# ============================================================================

@app.route('/stock')
def stock_management():
    """Render the Stock Management page."""
    active_products = service.get_all_products(include_archived=False)
    return render_template('stock_management.html',
                           products=active_products,
                           success_message=None,
                           error_message=None)


@app.route('/stock/in', methods=['POST'])
def stock_in():
    """
    Event-Driven: POST /stock/in triggers stock-in processing.
    """
    product_id = request.form.get('product_id', '')
    quantity = request.form.get('quantity', '')
    reason = request.form.get('reason', '')

    if not product_id:
        active_products = service.get_all_products(include_archived=False)
        return render_template('stock_management.html',
                               products=active_products,
                               success_message=None,
                               error_message='Please select a product.')

    success, message, new_qty = service.stock_in(int(product_id), quantity, reason)
    active_products = service.get_all_products(include_archived=False)
    return render_template('stock_management.html',
                           products=active_products,
                           success_message=message if success else None,
                           error_message=message if not success else None)


@app.route('/stock/out', methods=['POST'])
def stock_out():
    """
    Event-Driven: POST /stock/out triggers stock-out processing.
    """
    product_id = request.form.get('product_id', '')
    quantity = request.form.get('quantity', '')
    reason = request.form.get('reason', '')

    if not product_id:
        active_products = service.get_all_products(include_archived=False)
        return render_template('stock_management.html',
                               products=active_products,
                               success_message=None,
                               error_message='Please select a product.')

    success, message, new_qty = service.stock_out(int(product_id), quantity, reason)
    active_products = service.get_all_products(include_archived=False)
    return render_template('stock_management.html',
                           products=active_products,
                           success_message=message if success else None,
                           error_message=message if not success else None)


# ============================================================================
# TRANSACTIONS
# ============================================================================

@app.route('/transactions')
def transactions():
    """Display transaction history with filters."""
    product_id = request.args.get('product_id', '')
    txn_type = request.args.get('type', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    search = request.args.get('search', '').strip()
    sort_order = request.args.get('sort', 'DESC')

    txn_list = service.get_transactions(
        product_id=product_id if product_id else None,
        transaction_type=txn_type if txn_type else None,
        date_from=date_from if date_from else None,
        date_to=date_to if date_to else None,
        search=search,
        sort_order=sort_order,
    )
    all_products = service.get_all_products(include_archived=True)
    return render_template('transactions.html',
                           transactions=txn_list,
                           products=all_products,
                           filters={
                               'product_id': product_id,
                               'type': txn_type,
                               'date_from': date_from,
                               'date_to': date_to,
                               'search': search,
                               'sort': sort_order,
                           })


# ============================================================================
# REPORTS
# ============================================================================

@app.route('/reports')
def reports():
    """Render the Reports page with real data."""
    low_stock = service.get_low_stock_products()
    out_of_stock = service.get_out_of_stock_products()
    summary = service.get_inventory_summary()
    category_breakdown = service.get_category_breakdown()
    return render_template('reports.html',
                           low_stock=low_stock,
                           out_of_stock=out_of_stock,
                           summary=summary,
                           category_breakdown=category_breakdown)


@app.route('/reports/export/products')
def export_products():
    """Download products as CSV."""
    csv_data = service.export_products_csv()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=stockly_products.csv'}
    )


@app.route('/reports/export/transactions')
def export_transactions():
    """Download transactions as CSV."""
    csv_data = service.export_transactions_csv()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=stockly_transactions.csv'}
    )


# ============================================================================
# SETTINGS
# ============================================================================

@app.route('/settings')
def settings():
    """Display application settings and information."""
    app_info = {
        'name': 'Stockly',
        'tagline': 'Smarter Stock. Simpler Management.',
        'academic_title': ('Design and Development of Stockly – '
                           'A Web-Based Inventory and Resource Management System'),
        'currency': 'Indian Rupees (₹)',
        'currency_symbol': '₹',
        'categories': Product.CATEGORIES,
        'domain': 'Inventory Management',
        'target_users': 'Small retail business owners and inventory staff',
        'version': '1.0.0',
    }
    return render_template('settings.html', app_info=app_info)


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def page_not_found(e):
    flash('Page not found.', 'error')
    return redirect(url_for('dashboard'))


@app.errorhandler(500)
def internal_error(e):
    flash('An internal error occurred. Please try again.', 'error')
    return redirect(url_for('dashboard'))


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    print('=' * 60)
    print('  STOCKLY — Inventory & Resource Management System')
    print('  Smarter Stock. Simpler Management.')
    print('=' * 60)
    print('  Starting server at http://127.0.0.1:5000')
    print('=' * 60)
    app.run(debug=True, host='127.0.0.1', port=5000)

