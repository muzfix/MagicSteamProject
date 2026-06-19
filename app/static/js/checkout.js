(function () {
    var _token = localStorage.getItem('mtg_token');
    if (!_token) { window.location.href = '/auth/login?next=/checkout/' + _ORDER_ID; return; }

    function _authH() { return { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _token }; }

    function _esc(s) {
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    function _fmtDate(iso) {
        if (!iso) return '—';
        return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
    }

    function loadOrder() {
        fetch('/api/marketplace/orders/' + _ORDER_ID, { headers: { 'Authorization': 'Bearer ' + _token } })
            .then(function (r) {
                if (r.status === 401) { localStorage.removeItem('mtg_token'); window.location.href = '/auth/login'; return null; }
                if (!r.ok) { showMsg('Order not found.', true); return null; }
                return r.json();
            })
            .then(function (order) {
                if (!order) return;
                if (order.status !== 'pending') {
                    renderSummary(order);
                    showMsg('This order is already ' + order.status + '.', false);
                    document.getElementById('confirm-btn').disabled = true;
                    return;
                }
                renderSummary(order);
            });
    }

    function renderSummary(order) {
        var imgHtml = order.item_image
            ? '<img src="' + _esc(order.item_image) + '" class="w-16 rounded-lg shadow" alt="">'
            : '<div class="w-16 h-22 bg-gray-100 rounded-lg"></div>';

        document.getElementById('order-summary').innerHTML =
            '<div class="flex gap-4 items-start">' +
                imgHtml +
                '<div class="flex-1 min-w-0">' +
                    '<div class="font-semibold text-sm">' + _esc(order.item_name) + '</div>' +
                    (order.item_set ? '<div class="text-xs text-gray-500 mt-0.5">' + _esc(order.item_set) + '</div>' : '') +
                    '<div class="text-xs text-gray-400 mt-0.5">Order #' + order.id + ' &middot; ' + _fmtDate(order.created_at) + '</div>' +
                    '<div class="text-xs text-gray-500 mt-0.5">Seller: ' +
                        '<a href="/u/' + _esc(order.seller_username) + '" class="underline hover:text-gray-900">' +
                        _esc(order.seller_username) + '</a>' +
                    '</div>' +
                '</div>' +
                '<div class="text-right flex-shrink-0">' +
                    '<div class="text-lg font-bold">' + order.total_price.toFixed(3) + ' OMR</div>' +
                    '<div class="text-xs text-gray-400 mt-0.5">Qty ' + order.quantity + '</div>' +
                '</div>' +
            '</div>';
    }

    function getPickupLocation() {
        var radios = document.querySelectorAll('input[name="location"]');
        for (var i = 0; i < radios.length; i++) {
            if (radios[i].checked) {
                if (radios[i].value === 'other') {
                    return (document.getElementById('other-location-input').value || '').trim() || 'Other location';
                }
                return radios[i].value;
            }
        }
        return 'The Hearth';
    }

    function showMsg(text, isError) {
        var el = document.getElementById('checkout-msg');
        if (!el) return;
        el.textContent = text;
        el.className = 'text-sm text-center ' + (isError ? 'text-red-600' : 'text-green-700');
        el.classList.remove('hidden');
    }

    function init() {
        // Toggle "other location" text input
        document.querySelectorAll('input[name="location"]').forEach(function (r) {
            r.addEventListener('change', function () {
                var inp = document.getElementById('other-location-input');
                if (inp) inp.classList.toggle('hidden', r.value !== 'other');
            });
        });

        var confirmBtn = document.getElementById('confirm-btn');
        if (confirmBtn) {
            confirmBtn.addEventListener('click', function () {
                var pickup = getPickupLocation();
                if (!pickup) { showMsg('Please select a pickup location.', true); return; }
                confirmBtn.disabled = true;
                confirmBtn.textContent = 'Confirming…';

                fetch('/api/marketplace/orders/' + _ORDER_ID + '/cod', {
                    method: 'POST',
                    headers: _authH(),
                    body: JSON.stringify({ pickup_location: pickup }),
                })
                .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
                .then(function (res) {
                    if (res.ok) {
                        confirmBtn.textContent = 'Confirmed!';
                        showMsg('Order confirmed! Arrange pickup at: ' + pickup + '. Check My Orders for status.', false);
                        setTimeout(function () { window.location.href = '/my-orders'; }, 2000);
                    } else {
                        confirmBtn.disabled = false;
                        confirmBtn.textContent = 'Confirm Order';
                        showMsg(res.d.detail || 'Failed to confirm order.', true);
                    }
                })
                .catch(function () {
                    confirmBtn.disabled = false;
                    confirmBtn.textContent = 'Confirm Order';
                    showMsg('Network error. Please try again.', true);
                });
            });
        }

        loadOrder();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
