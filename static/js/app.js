/**
 * Stockly — Enterprise Client-Side Interaction Controller
 * ========================================================
 * PROGRAMMING PARADIGM: Event-Driven Programming
 *
 * Implements client-side event handlers:
 * - Responsive mobile navigation drawer toggle and backdrop dismissal
 * - Search debouncing (600ms) for responsive filtering without jarring reload
 * - Filter dropdown auto-submission
 * - Live stock preview indicator during Stock In / Stock Out item selection
 * - Safe archive confirmation modal prompt
 * - Automatic graceful dismissal of status alert notifications
 */

document.addEventListener('DOMContentLoaded', () => {
    // ====================================================================
    // 1. Mobile Sidebar Navigation & Backdrop Overlay
    // ====================================================================
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    const sidebarOverlay = document.querySelector('.sidebar-overlay');

    function toggleSidebar(open) {
        if (!sidebar) return;
        const isOpen = open !== undefined ? open : !sidebar.classList.contains('open');
        sidebar.classList.toggle('open', isOpen);
        if (sidebarOverlay) {
            sidebarOverlay.classList.toggle('active', isOpen);
        }
    }

    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleSidebar();
        });
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', () => toggleSidebar(false));
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sidebar && sidebar.classList.contains('open')) {
            toggleSidebar(false);
        }
    });

    // ====================================================================
    // 2. Alert Notification Dismissal
    // ====================================================================
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach((alert) => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-6px)';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });

    // ====================================================================
    // 3. Product Archive Confirmation
    // ====================================================================
    const archiveForms = document.querySelectorAll('.archive-form');
    archiveForms.forEach((form) => {
        form.addEventListener('submit', (e) => {
            const productName = form.dataset.productName || 'this item';
            const confirmed = window.confirm(
                `Are you sure you want to archive "${productName}"?\n\nThe product will be hidden from active inventory actions, but its historical audit logs will be permanently preserved.`
            );
            if (!confirmed) {
                e.preventDefault();
            }
        });
    });

    // ====================================================================
    // 4. Filter Auto-Submission & Search Debounce
    // ====================================================================
    const filterSelects = document.querySelectorAll('.filter-card select, .filter-bar select');
    filterSelects.forEach((select) => {
        select.addEventListener('change', function () {
            this.closest('form').submit();
        });
    });

    const archivedCheckbox = document.getElementById('show-archived');
    if (archivedCheckbox) {
        archivedCheckbox.addEventListener('change', function () {
            this.closest('form').submit();
        });
    }

    const searchInputs = document.querySelectorAll('.search-input');
    let searchTimer = null;
    searchInputs.forEach((input) => {
        input.addEventListener('input', function () {
            clearTimeout(searchTimer);
            const form = this.closest('form');
            if (form) {
                searchTimer = setTimeout(() => {
                    form.submit();
                }, 600);
            }
        });
    });

    // ====================================================================
    // 5. Stock Management Dynamic Preview
    // ====================================================================
    const stockSelects = document.querySelectorAll('.stock-product-select');
    stockSelects.forEach((select) => {
        function updateLivePreview() {
            const selectedOpt = select.options[select.selectedIndex];
            const liveBadge = select.closest('.form-group')?.querySelector('.stock-live-badge');
            const targetQtySpan = liveBadge?.querySelector('.live-qty-value');

            if (liveBadge && targetQtySpan) {
                if (selectedOpt && selectedOpt.value) {
                    const availableQty = selectedOpt.dataset.quantity ?? '0';
                    targetQtySpan.textContent = `${availableQty} units`;
                    liveBadge.style.display = 'flex';
                } else {
                    liveBadge.style.display = 'none';
                }
            }
        }

        select.addEventListener('change', updateLivePreview);
        updateLivePreview();
    });

    // ====================================================================
    // 6. Form Submission Validation Guards
    // ====================================================================
    const productForm = document.getElementById('product-form');
    if (productForm) {
        productForm.addEventListener('submit', (e) => {
            const name = document.getElementById('name');
            const sku = document.getElementById('sku');
            const price = document.getElementById('price');
            const errors = [];

            if (name && !name.value.trim()) errors.push('Product name is required.');
            if (sku && !sku.value.trim()) errors.push('SKU is required.');
            if (price && (isNaN(parseFloat(price.value)) || parseFloat(price.value) < 0)) {
                errors.push('Unit price cannot be negative.');
            }

            if (errors.length > 0) {
                e.preventDefault();
                showClientNotice(errors);
            }
        });
    }

    const stockForms = document.querySelectorAll('.stock-form');
    stockForms.forEach((form) => {
        form.addEventListener('submit', (e) => {
            const select = form.querySelector('select[name="product_id"]');
            const qtyInput = form.querySelector('input[name="quantity"]');
            const errors = [];

            if (!select || !select.value) {
                errors.push('Please select a product.');
            }
            if (qtyInput) {
                const qty = parseInt(qtyInput.value, 10);
                if (isNaN(qty) || qty <= 0) {
                    errors.push('Quantity must be a positive integer greater than zero.');
                }
            }

            if (errors.length > 0) {
                e.preventDefault();
                showClientNotice(errors);
            }
        });
    });

    function showClientNotice(messages) {
        const oldNotice = document.getElementById('client-notice');
        if (oldNotice) oldNotice.remove();

        const notice = document.createElement('div');
        notice.id = 'client-notice';
        notice.className = 'alert alert-danger';
        notice.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <div>
                <strong>Please correct the following:</strong><br>
                ${messages.map(m => `• ${m}`).join('<br>')}
            </div>
        `;

        const content = document.querySelector('.main-content');
        if (content) {
            content.insertBefore(notice, content.firstChild);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    }
});
