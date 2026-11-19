/**
 * Stockly — Client Interaction & Reactive Workspace Controller
 * =============================================================
 * PROGRAMMING PARADIGM: Event-Driven Programming
 *
 * All UI behaviors are driven by event listeners attached to DOM elements.
 * Features:
 * - Responsive mobile drawer toggle & backdrop dismiss
 * - Segmented tab switcher for Stock In / Stock Out console
 * - Real-time Product Form live preview updates
 * - Dynamic stock calculator on Stock Management (Current vs Projected Balance)
 * - Search debouncing (500ms)
 * - Filter dropdown auto-submission
 * - Archive confirmation prompt
 * - Collapsible filter drawer for transaction date ranges
 * - Auto-dismissing alerts
 */

document.addEventListener('DOMContentLoaded', () => {

    // ====================================================================
    // 1. Mobile Sidebar Navigation Drawer & Backdrop
    // ====================================================================
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    const sidebarOverlay = document.querySelector('.sidebar-overlay');

    function toggleSidebar(open) {
        if (!sidebar) return;
        const isOpen = open !== undefined ? open : !sidebar.classList.contains('open');
        sidebar.classList.toggle('open', isOpen);
        if (sidebarToggle) sidebarToggle.setAttribute('aria-expanded', String(isOpen));
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
    // 2. Alert Dismissal with Smooth Fade
    // ====================================================================
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach((alert) => {
        if (alert.classList.contains('alert-danger') || alert.classList.contains('alert-error')) return;
        setTimeout(() => {
            alert.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-6px)';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });

    // ====================================================================
    // 3. Product Archive Confirmation Guard
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
    // 4. Filter Auto-Submit & Search Debounce
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
                }, 500);
            }
        });
    });

    // ====================================================================
    // 5. Stock Management Segmented Tab Controller
    // ====================================================================
    const tabIn = document.getElementById('tab-stock-in');
    const tabOut = document.getElementById('tab-stock-out');
    const panelIn = document.getElementById('panel-stock-in');
    const panelOut = document.getElementById('panel-stock-out');

    if (tabIn && tabOut && panelIn && panelOut) {
        tabIn.addEventListener('click', () => {
            tabIn.classList.add('active-in');
            tabOut.classList.remove('active-out');
            panelIn.classList.add('active');
            panelOut.classList.remove('active');
            updateStockInspector('IN');
        });

        tabOut.addEventListener('click', () => {
            tabOut.classList.add('active-out');
            tabIn.classList.remove('active-in');
            panelOut.classList.add('active');
            panelIn.classList.remove('active');
            updateStockInspector('OUT');
        });
    }

    // ====================================================================
    // 6. Interactive Stock Inspector & Projected Balance Calculator
    // ====================================================================
    function updateStockInspector(currentMode) {
        const activePanel = document.querySelector('.stock-form-panel.active') || panelIn;
        if (!activePanel) return;

        const select = activePanel.querySelector('.stock-product-select');
        const qtyInput = activePanel.querySelector('input[name="quantity"]');
        const selectedOpt = select ? select.options[select.selectedIndex] : null;

        const nameEl = document.getElementById('inspector-product-name');
        const skuEl = document.getElementById('inspector-product-sku');
        const stockEl = document.getElementById('inspector-current-stock');
        const reorderEl = document.getElementById('inspector-reorder-level');
        const projectedEl = document.getElementById('inspector-projected-stock');
        const statusEl = document.getElementById('inspector-status-badge');
        const meterFill = document.getElementById('inspector-meter-fill');

        if (selectedOpt && selectedOpt.value) {
            const productName = selectedOpt.dataset.name || selectedOpt.text.split('(')[0].trim();
            const sku = selectedOpt.dataset.sku || 'SKU-N/A';
            const currentQty = parseInt(selectedOpt.dataset.quantity || '0', 10);
            const reorderLvl = parseInt(selectedOpt.dataset.reorder || '10', 10);
            const rawMoveQty = qtyInput && qtyInput.value ? qtyInput.value.trim() : '';
            const validMoveQty = rawMoveQty === '' || /^\d+$/.test(rawMoveQty);
            const moveQty = /^\d+$/.test(rawMoveQty) ? Number(rawMoveQty) : 0;

            if (nameEl) nameEl.textContent = productName;
            if (skuEl) skuEl.textContent = sku;
            if (stockEl) stockEl.textContent = `${currentQty} units`;
            if (reorderEl) reorderEl.textContent = `${reorderLvl} units`;

            // Calculate Projected Balance
            const isStockIn = activePanel.id === 'panel-stock-in';
            const insufficient = !isStockIn && moveQty > currentQty;
            const projected = currentQty - moveQty;
            if (projectedEl) {
                projectedEl.textContent = !validMoveQty ? 'Enter a whole number' : (insufficient ? 'Insufficient stock' : `${isStockIn ? currentQty + moveQty : projected} units`);
                projectedEl.style.color = insufficient ? 'var(--danger)' : (isStockIn ? 'var(--success)' : (projected <= reorderLvl ? 'var(--danger)' : 'var(--text-primary)'));
            }

            // Update Status Badge
            if (statusEl) {
                if (currentQty === 0) {
                    statusEl.className = 'badge badge-danger';
                    statusEl.textContent = 'Out of Stock';
                } else if (currentQty <= reorderLvl) {
                    statusEl.className = 'badge badge-warning';
                    statusEl.textContent = 'Low Stock';
                } else {
                    statusEl.className = 'badge badge-success';
                    statusEl.textContent = 'In Stock';
                }
            }

            // Update Mini Meter
            if (meterFill) {
                const maxMeter = Math.max(reorderLvl * 2, currentQty, 20);
                const pct = Math.min(100, Math.round((currentQty / maxMeter) * 100));
                meterFill.style.width = `${pct}%`;
                meterFill.style.backgroundColor = currentQty === 0 ? 'var(--danger)' : (currentQty <= reorderLvl ? 'var(--warning)' : 'var(--success)');
            }
        } else {
            if (nameEl) nameEl.textContent = 'No product selected';
            if (skuEl) skuEl.textContent = 'Select a product from the dropdown';
            if (stockEl) stockEl.textContent = '—';
            if (reorderEl) reorderEl.textContent = '—';
            if (projectedEl) projectedEl.textContent = '—';
            if (statusEl) {
                statusEl.className = 'badge badge-secondary';
                statusEl.textContent = 'Select Product';
            }
            if (meterFill) {
                meterFill.style.width = '0%';
                meterFill.style.backgroundColor = 'var(--border-color)';
            }
        }
    }

    const stockSelects = document.querySelectorAll('.stock-product-select');
    stockSelects.forEach((sel) => {
        sel.addEventListener('change', () => updateStockInspector());
    });

    const stockQtyInputs = document.querySelectorAll('.stock-form input[name="quantity"]');
    stockQtyInputs.forEach((inp) => {
        inp.addEventListener('input', () => updateStockInspector());
    });

    // Run initial inspector state
    updateStockInspector();

    // ====================================================================
    // 7. Product Form Live Preview Updates (Add / Edit Page)
    // ====================================================================
    const formNameInput = document.getElementById('name');
    const formSkuInput = document.getElementById('sku');
    const formCategorySelect = document.getElementById('category');
    const formPriceInput = document.getElementById('price');
    const formQtyInput = document.getElementById('quantity');
    const formReorderInput = document.getElementById('reorder_level');

    const previewName = document.getElementById('preview-name');
    const previewSku = document.getElementById('preview-sku');
    const previewCategory = document.getElementById('preview-category');
    const previewPrice = document.getElementById('preview-price');
    const previewStock = document.getElementById('preview-stock');
    const previewStatus = document.getElementById('preview-status');
    const previewReorder = document.getElementById('preview-reorder');

    function updateProductLivePreview() {
        if (!previewName) return;

        const nameVal = formNameInput && formNameInput.value.trim() ? formNameInput.value.trim() : 'Product Title';
        const skuVal = formSkuInput && formSkuInput.value.trim() ? formSkuInput.value.trim() : 'SKU-SAMPLE';
        const catVal = formCategorySelect ? formCategorySelect.value : 'General';
        const priceVal = formPriceInput && !isNaN(parseFloat(formPriceInput.value)) ? parseFloat(formPriceInput.value).toFixed(2) : '0.00';
        const existingQty = Number(previewStock && previewStock.dataset.quantity);
        const qtyText = formQtyInput ? formQtyInput.value.trim() : '';
        const reorderText = formReorderInput ? formReorderInput.value.trim() : '';
        const editMode = !formQtyInput;
        const existingQtyValid = Number.isInteger(existingQty) && existingQty >= 0;
        const qtyValid = editMode ? existingQtyValid : /^\d+$/.test(qtyText);
        const reorderValid = /^\d+$/.test(reorderText);
        const qtyVal = editMode ? existingQty : (qtyValid ? Number(qtyText) : 0);
        const reorderVal = reorderValid ? Number(reorderText) : 10;

        previewName.textContent = nameVal;
        previewSku.textContent = skuVal;
        if (previewCategory) previewCategory.textContent = catVal;
        if (previewPrice) previewPrice.textContent = `₹${Number(priceVal).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
        if (previewStock) previewStock.textContent = qtyValid ? `${qtyVal} units` : 'Invalid quantity';
        if (previewReorder) previewReorder.textContent = reorderValid ? `${reorderVal} units` : 'Invalid level';

        if (previewStatus) {
            if (!qtyValid || !reorderValid) {
                previewStatus.className = 'badge badge-danger';
                previewStatus.textContent = 'Invalid input';
            } else if (qtyVal === 0) {
                previewStatus.className = 'badge badge-danger';
                previewStatus.textContent = 'Out of Stock';
            } else if (qtyVal <= reorderVal) {
                previewStatus.className = 'badge badge-warning';
                previewStatus.textContent = 'Low Stock Alert';
            } else {
                previewStatus.className = 'badge badge-success';
                previewStatus.textContent = 'In Stock';
            }
        }
    }

    if (formNameInput) formNameInput.addEventListener('input', updateProductLivePreview);
    if (formSkuInput) formSkuInput.addEventListener('input', updateProductLivePreview);
    if (formCategorySelect) formCategorySelect.addEventListener('change', updateProductLivePreview);
    if (formPriceInput) formPriceInput.addEventListener('input', updateProductLivePreview);
    if (formQtyInput) formQtyInput.addEventListener('input', updateProductLivePreview);
    if (formReorderInput) formReorderInput.addEventListener('input', updateProductLivePreview);

    updateProductLivePreview();

    // ====================================================================
    // 8. Collapsible Filter Toggle for Transactions
    // ====================================================================
    const filterToggleBtn = document.getElementById('toggle-advanced-filters');
    const advancedFiltersRow = document.getElementById('advanced-filters-row');
    if (filterToggleBtn && advancedFiltersRow) {
        filterToggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const isHidden = advancedFiltersRow.style.display === 'none';
            advancedFiltersRow.style.display = isHidden ? 'flex' : 'none';
            filterToggleBtn.classList.toggle('active', isHidden);
        });
    }
});
