"""
Stockly — Flask Application
=============================
Main entry point. Defines all HTTP routes and connects the browser UI
to the InventoryService business-logic layer.

PROGRAMMING PARADIGM: Event-Driven (HTTP request → route handler → response)
Each Flask route is an event handler triggered by a browser request.
"""

import os
import logging
import secrets
from datetime import datetime
from flask import (Flask, current_app, render_template, request, redirect,
                   url_for, flash, Response)
from inventory_service import InventoryService
from models import Product
from utils import format_currency, format_datetime, format_stock_status

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application factory & Configuration
# ---------------------------------------------------------------------------
app = Flask(__name__)
# Secure secret key with safe local dev fallback
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

# Create the shared service instance
service = InventoryService()
app.extensions['inventory_service'] = service


def get_service():
    """Resolve the injected service for the current Flask application."""
    return current_app.extensions['inventory_service']


def create_app(service_instance=None):
    """Create an independently configured Flask application instance."""
    application = Flask(__name__)
    application.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    application.extensions['inventory_service'] = (
        service_instance or InventoryService()
    )
    application.jinja_env.filters.update({
        'currency': format_currency,
        'datefmt': format_datetime,
        'stockstatus': format_stock_status,
    })
    application.context_processor(inject_global_context)
    for rule in app.url_map.iter_rules():
        if rule.endpoint == 'static':
            continue
        application.add_url_rule(
            rule.rule,
            endpoint=rule.endpoint,
            view_func=app.view_functions[rule.endpoint],
            methods=list(rule.methods - {'HEAD', 'OPTIONS'}),
            defaults=rule.defaults,
        )
    application.errorhandler(404)(page_not_found)
    application.errorhandler(500)(internal_error)
    return application

# ---------------------------------------------------------------------------
# Jinja2 custom filters & context processors
# ---------------------------------------------------------------------------
app.jinja_env.filters['currency'] = format_currency
app.jinja_env.filters['datefmt'] = format_datetime
app.jinja_env.filters['stockstatus'] = format_stock_status


@app.context_processor
def inject_global_context():
    """Inject only values shared by every page."""
    return {'cache_bust': '2.3.0'}


# ============================================================================
# DASHBOARD
# ============================================================================

@app.route('/')
def dashboard():
    """
    Event-Driven: GET / triggers dashboard rendering.
    Calculates KPI metrics, 7-day movement data, and health breakdown from SQLite.
    """
    stats = get_service().get_dashboard_stats()
    low_stock = get_service().get_low_stock_products()
    recent_txns = get_service().get_recent_transactions(limit=6)
    health_stats = get_service().get_inventory_health_stats()
    movement_stats = get_service().get_daily_movement_stats(days=7)
    has_demo_activity = get_service().has_demo_activity()

    return render_template('dashboard.html',
                           stats=stats,
                           low_stock_products=low_stock,
                           recent_transactions=recent_txns,
                           health_stats=health_stats,
                           movement_stats=movement_stats,
                           has_demo_activity=has_demo_activity)


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

    product_list = get_service().search_products(
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
        product_id, errors = get_service().add_product(data)
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
    product = get_service().get_product(product_id)
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
        success, errors = get_service().update_product(product_id, data)
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
    success, error = get_service().archive_product(product_id)
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
    active_products = get_service().get_all_products(include_archived=False)
    mode = request.args.get('mode', 'in')
    if mode not in ('in', 'out'):
        mode = 'in'
    return render_template('stock_management.html',
                           products=active_products,
                           mode=mode,
                           success_message=None,
                           error_message=None)


@app.route('/stock/in', methods=['POST'])
def stock_in():
    """
    Event-Driven: POST /stock/in triggers stock-in processing.
    """
    product_id_raw = (request.form.get('product_id') or '').strip()
    quantity = request.form.get('quantity', '')
    reason = request.form.get('reason', '')

    if not product_id_raw or not product_id_raw.isdigit() or int(product_id_raw) <= 0:
        flash('Please select a valid product.', 'error')
        return redirect(url_for('stock_management', mode='in'))

    success, message, new_qty = get_service().stock_in(int(product_id_raw), quantity, reason)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('stock_management', mode='in'))


@app.route('/stock/out', methods=['POST'])
def stock_out():
    """
    Event-Driven: POST /stock/out triggers stock-out processing.
    """
    product_id_raw = (request.form.get('product_id') or '').strip()
    quantity = request.form.get('quantity', '')
    reason = request.form.get('reason', '')

    if not product_id_raw or not product_id_raw.isdigit() or int(product_id_raw) <= 0:
        flash('Please select a valid product.', 'error')
        return redirect(url_for('stock_management', mode='out'))

    success, message, new_qty = get_service().stock_out(int(product_id_raw), quantity, reason)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('stock_management', mode='out'))


# ============================================================================
# TRANSACTIONS
# ============================================================================

@app.route('/transactions')
def transactions():
    """Display transaction history with filters."""
    product_id = request.args.get('product_id', '').strip()
    txn_type = request.args.get('type', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    search = request.args.get('search', '').strip()
    sort_order = request.args.get('sort', 'DESC')
    if product_id and (not product_id.isdigit() or int(product_id) <= 0):
        product_id = ''
        flash('Invalid product filter ignored.', 'error')
    if txn_type not in ('', 'STOCK_IN', 'STOCK_OUT', 'OPENING'):
        txn_type = ''
        flash('Invalid movement filter ignored.', 'error')
    for field_name, value in (('date_from', date_from), ('date_to', date_to)):
        if value:
            try:
                datetime.strptime(value, '%Y-%m-%d')
            except ValueError:
                flash(f'Invalid {field_name.replace("_", " ")} filter ignored.', 'error')
                if field_name == 'date_from':
                    date_from = ''
                else:
                    date_to = ''
    if date_from and date_to and date_from > date_to:
        flash('Date From cannot be later than Date To.', 'error')
        date_from = ''
        date_to = ''
    if sort_order.upper() not in ('ASC', 'DESC', 'OLDEST', 'NEWEST'):
        sort_order = 'DESC'
        flash('Invalid sort order ignored.', 'error')

    txn_list = get_service().get_transactions(
        product_id=product_id if product_id else None,
        transaction_type=txn_type if txn_type else None,
        date_from=date_from if date_from else None,
        date_to=date_to if date_to else None,
        search=search,
        sort_order=sort_order,
    )
    all_products = get_service().get_all_products(include_archived=True)
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
    low_stock = get_service().get_low_stock_products()
    out_of_stock = get_service().get_out_of_stock_products()
    summary = get_service().get_inventory_summary()
    category_breakdown = get_service().get_category_breakdown()
    return render_template('reports.html',
                           low_stock=low_stock,
                           out_of_stock=out_of_stock,
                           summary=summary,
                           category_breakdown=category_breakdown)


@app.route('/reports/export/products')
def export_products():
    """Download products as CSV."""
    csv_data = get_service().export_products_csv()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=stockly_products.csv'}
    )


@app.route('/reports/export/transactions')
def export_transactions():
    """Download transactions as CSV."""
    csv_data = get_service().export_transactions_csv()
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
        'edition': 'Enterprise Edition',
        'currency': 'INR (₹)',
        'currency_symbol': '₹',
        'categories': Product.CATEGORIES,
        'description': 'A local-first inventory management workspace for tracking products, stock movements, and reports.',
        'version': '2.2.0',
    }
    return render_template('settings.html', app_info=app_info)


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(e):
    logger.exception('Unhandled application error')
    return render_template('500.html'), 500


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1')
    print('=' * 60)
    print('  STOCKLY — Inventory & Resource Management System')
    print('  Smarter Stock. Simpler Management.')
    print('=' * 60)
    print(f'  Starting server at http://127.0.0.1:5000 (Debug: {debug_mode})')
    print('=' * 60)
    app.run(debug=debug_mode, host='127.0.0.1', port=5000)
