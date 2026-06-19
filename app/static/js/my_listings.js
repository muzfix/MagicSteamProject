(function () {
    var _token = localStorage.getItem('mtg_token');
    if (!_token) { window.location.href = '/auth/login?next=/my-listings'; return; }

    var _showAll = false;
    var _allListings = [];

    function _authH() { return { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _token }; }

    function _esc(s) {
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    function _fmtDate(iso) {
        if (!iso) return '—';
        return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
    }

    function setTab(tab) {
        _showAll = tab === 'all';
        document.getElementById('tab-active').className =
            'px-3 py-1.5 rounded-full font-semibold text-xs transition-colors ' +
            (!_showAll ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200');
        document.getElementById('tab-all').className =
            'px-3 py-1.5 rounded-full font-semibold text-xs transition-colors ' +
            (_showAll ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200');
        render();
    }
    window.setTab = setTab;

    function render() {
        var items = _showAll ? _allListings : _allListings.filter(function (l) { return l.is_active === 1; });
        var count = document.getElementById('listings-count');
        if (count) count.textContent = items.length + ' listing' + (items.length !== 1 ? 's' : '');

        var c = document.getElementById('listings-container');
        if (!items.length) {
            c.innerHTML = '<div class="py-16 text-center text-sm text-gray-400">No listings' +
                (!_showAll ? ' — <a href="/sell" class="underline text-gray-700">list a card</a>' : '') + '</div>';
            return;
        }

        c.innerHTML = items.map(function (l) {
            var activeBadge = l.is_active === 1
                ? '<span class="text-[10px] font-semibold text-green-700 bg-green-100 px-1.5 py-0.5 rounded">Active</span>'
                : '<span class="text-[10px] font-semibold text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">Inactive</span>';
            var pendingBadge = l.pending_orders > 0
                ? '<span class="text-[10px] font-semibold text-blue-700 bg-blue-100 px-1.5 py-0.5 rounded ml-1">' + l.pending_orders + ' order' + (l.pending_orders > 1 ? 's' : '') + '</span>'
                : '';
            var actions = l.is_active === 1
                ? '<button onclick="openEditModal(' + JSON.stringify(l).replace(/</g,'\\u003c') + ')" ' +
                  'class="text-xs border border-gray-300 rounded px-2 py-0.5 hover:bg-gray-100 transition-colors">Edit</button>' +
                  '<button onclick="deactivate(' + l.id + ')" ' +
                  'class="text-xs text-red-600 border border-red-200 rounded px-2 py-0.5 hover:bg-red-50 transition-colors ml-1">Remove</button>'
                : '';
            return '<div class="py-4 flex items-center gap-4" id="listing-row-' + l.id + '">' +
                (l.image_uri ? '<img src="' + _esc(l.image_uri) + '" class="w-12 rounded shadow-sm flex-shrink-0" alt="">' :
                    '<div class="w-12 h-16 bg-gray-100 rounded flex-shrink-0"></div>') +
                '<div class="flex-1 min-w-0">' +
                    '<div class="font-medium text-sm">' + _esc(l.card_name) + '</div>' +
                    '<div class="text-xs text-gray-500 mt-0.5">' + _esc(l.set_name) + ' &middot; ' + _esc(l.condition) + '</div>' +
                    '<div class="flex items-center gap-1 mt-1">' + activeBadge + pendingBadge + '</div>' +
                    '<div class="text-xs text-gray-400 mt-0.5">' + _fmtDate(l.created_at) + '</div>' +
                '</div>' +
                '<div class="text-right flex-shrink-0 space-y-1">' +
                    '<div class="font-semibold text-sm">' + l.price.toFixed(3) + ' OMR</div>' +
                    '<div class="text-xs text-gray-400">Qty ' + l.quantity + '</div>' +
                    '<div class="flex gap-1 justify-end">' + actions + '</div>' +
                '</div>' +
                '</div>';
        }).join('');
    }

    window.openEditModal = function (listing) {
        document.getElementById('edit-listing-id').value = listing.id;
        document.getElementById('edit-price').value = listing.price.toFixed(3);
        document.getElementById('edit-qty').value = listing.quantity;
        document.getElementById('edit-desc').value = listing.description || '';
        var msg = document.getElementById('edit-msg');
        if (msg) { msg.className = 'hidden text-xs'; msg.textContent = ''; }
        document.getElementById('edit-modal').classList.remove('hidden');
    };

    window.closeEditModal = function () {
        document.getElementById('edit-modal').classList.add('hidden');
    };

    window.deactivate = function (listingId) {
        if (!confirm('Remove this listing?')) return;
        fetch('/api/marketplace/listings/' + listingId, { method: 'DELETE', headers: _authH() })
            .then(function (r) {
                if (r.ok || r.status === 204) {
                    var row = document.getElementById('listing-row-' + listingId);
                    if (row) row.remove();
                    _allListings = _allListings.map(function (l) {
                        return l.id === listingId ? Object.assign({}, l, { is_active: 0 }) : l;
                    });
                    render();
                }
            });
    };

    function initEditSave() {
        var btn = document.getElementById('edit-save-btn');
        if (!btn) return;
        btn.addEventListener('click', function () {
            var id = parseInt(document.getElementById('edit-listing-id').value);
            var price = parseFloat(document.getElementById('edit-price').value);
            var qty = parseInt(document.getElementById('edit-qty').value);
            var desc = document.getElementById('edit-desc').value.trim();
            var msg = document.getElementById('edit-msg');

            if (!price || price <= 0) { showEditMsg('Enter a valid price.', true); return; }
            if (!qty || qty < 1) { showEditMsg('Enter a valid quantity.', true); return; }

            btn.disabled = true;
            fetch('/api/marketplace/listings/' + id, {
                method: 'PATCH',
                headers: _authH(),
                body: JSON.stringify({ price: price, quantity: qty, description: desc || null }),
            })
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
            .then(function (res) {
                btn.disabled = false;
                if (res.ok) {
                    _allListings = _allListings.map(function (l) {
                        return l.id === id ? Object.assign({}, l, { price: price, quantity: qty, description: desc || null }) : l;
                    });
                    closeEditModal();
                    render();
                } else {
                    showEditMsg(res.d.detail || 'Failed to update.', true);
                }
            })
            .catch(function () { btn.disabled = false; showEditMsg('Network error.', true); });
        });
    }

    function showEditMsg(text, isError) {
        var el = document.getElementById('edit-msg');
        if (!el) return;
        el.textContent = text;
        el.className = 'text-xs ' + (isError ? 'text-red-600' : 'text-green-700');
        el.classList.remove('hidden');
    }

    function load() {
        fetch('/api/marketplace/listings/mine', { headers: { 'Authorization': 'Bearer ' + _token } })
            .then(function (r) {
                if (r.status === 401) { localStorage.removeItem('mtg_token'); window.location.href = '/auth/login'; return null; }
                return r.json();
            })
            .then(function (d) {
                if (!d) return;
                _allListings = d.listings || [];
                render();
            })
            .catch(function () {
                document.getElementById('listings-container').innerHTML =
                    '<div class="py-8 text-center text-sm text-red-500">Failed to load listings.</div>';
            });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { initEditSave(); load(); });
    } else {
        initEditSave(); load();
    }
})();
