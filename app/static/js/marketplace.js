(function () {
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('.buy-btn');
        if (!btn) return;

        var listingId = btn.dataset.listingId;
        if (!listingId) return;

        var token = localStorage.getItem('mtg_token');
        if (!token) {
            window.location.href = '/auth/login?next=/marketplace';
            return;
        }

        btn.disabled = true;
        btn.textContent = '...';

        fetch('/api/marketplace/orders', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token,
            },
            body: JSON.stringify({ listing_id: parseInt(listingId, 10), quantity: 1 }),
        })
        .then(function (r) {
            return r.json().then(function (d) { return { ok: r.ok, d: d }; });
        })
        .then(function (res) {
            if (res.ok) {
                alert('Order placed! The seller will be in touch.');
                location.reload();
            } else {
                alert(res.d.detail || 'Could not place order.');
                btn.disabled = false;
                btn.textContent = 'Buy';
            }
        })
        .catch(function () {
            alert('Network error. Please try again.');
            btn.disabled = false;
            btn.textContent = 'Buy';
        });
    });
})();
