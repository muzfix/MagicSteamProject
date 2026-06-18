(function () {
    // ── State ──────────────────────────────────────────────────────────────────
    var _cart        = [];   // [{scryfallId, name, set, img, foilLabel}]
    var _cartSet     = {};   // scryfallId → true
    var _cartDetails = {};   // scryfallId → {price, condition, qty, notes}

    var _currentVariants = [];
    var _szIdx           = 0;
    var _szFlipped       = false;  // true when sell-zoom is showing the DFC back face
    var _spCardEl        = null;   // the .card-option element currently in preview

    var _CART_KEY   = 'mtg_sell_cart_v1';
    var _SEARCH_KEY = 'mtg_sell_search_v1';

    // ── localStorage persistence ───────────────────────────────────────────────

    function _saveCart() {
        try {
            localStorage.setItem(_CART_KEY, JSON.stringify({
                cart:    _cart,
                details: _cartDetails,
            }));
        } catch (_) {}
    }

    function _clearCartStorage() {
        try { localStorage.removeItem(_CART_KEY); } catch (_) {}
    }

    function _syncCartDetails() {
        document.querySelectorAll('.cart-item').forEach(function (row) {
            var idx  = parseInt(row.dataset.idx, 10);
            var item = _cart[idx];
            if (!item) return;
            _cartDetails[item.scryfallId] = {
                price:     (row.querySelector('.item-price')     || {}).value || '',
                condition: (row.querySelector('.item-condition') || {}).value || 'NM',
                qty:       (row.querySelector('.item-qty')       || {}).value || '1',
                notes:     (row.querySelector('.item-notes')     || {}).value || '',
            };
        });
    }

    function _restoreCartDetails() {
        document.querySelectorAll('.cart-item').forEach(function (row) {
            var idx  = parseInt(row.dataset.idx, 10);
            var item = _cart[idx];
            if (!item) return;
            var d = _cartDetails[item.scryfallId];
            if (!d) return;
            var inp   = row.querySelector('.item-price');
            var cond  = row.querySelector('.item-condition');
            var qty   = row.querySelector('.item-qty');
            var notes = row.querySelector('.item-notes');
            if (inp   && d.price)     inp.value   = d.price;
            if (cond  && d.condition) cond.value  = d.condition;
            if (qty   && d.qty)       qty.value   = d.qty;
            if (notes && d.notes)     notes.value = d.notes;
        });
    }

    function _loadCart() {
        try {
            var raw = localStorage.getItem(_CART_KEY);
            if (!raw) return;
            var saved = JSON.parse(raw);
            if (!saved || !Array.isArray(saved.cart) || !saved.cart.length) return;
            _cart    = saved.cart;
            _cartSet = {};
            _cart.forEach(function (c) { _cartSet[c.scryfallId] = true; });
            _cartDetails = saved.details || {};
            _renderCart();
            _restoreCartDetails();
        } catch (_) {}
    }

    function _loadSearch() {
        var el = document.getElementById('card-search');
        if (!el) return;
        var saved = '';
        try { saved = localStorage.getItem(_SEARCH_KEY) || ''; } catch (_) {}
        if (!saved || saved.length < 2) return;
        el.value = saved;
        // Trigger HTMX search — almost certainly a cache hit, so zero extra DB work
        setTimeout(function () {
            el.dispatchEvent(new Event('input', { bubbles: true }));
        }, 80);
    }

    // ── Utilities ──────────────────────────────────────────────────────────────

    function _esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function _toast(msg) {
        var t = document.getElementById('cart-toast');
        if (!t) return;
        t.textContent = msg;
        t.classList.remove('hidden');
        clearTimeout(t._tid);
        t._tid = setTimeout(function () { t.classList.add('hidden'); }, 2200);
    }

    function _hideCartMessages() {
        var err = document.getElementById('cart-error');
        var ok  = document.getElementById('cart-success');
        if (err) err.classList.add('hidden');
        if (ok)  ok.classList.add('hidden');
    }

    function _showCartError(msg) {
        var el = document.getElementById('cart-error');
        if (!el) return;
        el.textContent = msg;
        el.classList.remove('hidden');
    }

    function _parseVariants(card) {
        try {
            return JSON.parse(card.dataset.variants || '[]');
        } catch (_) {
            return [{
                id:          card.dataset.scryfallId || '',
                name:        card.dataset.name       || '',
                set:         card.dataset.set        || '',
                img:         card.dataset.image      || '',
                img_hd:      card.dataset.image      || '',
                price:       '',
                foil_label:  '',
                listing_cnt: 0,
            }];
        }
    }

    // ── Sell-preview panel ─────────────────────────────────────────────────────

    function _variantRowHTML(v, idx) {
        var inCart    = !!_cartSet[v.id];
        var foilHtml  = v.foil_label
            ? '<span class="ml-1 text-[10px] font-semibold text-purple-600">' + _esc(v.foil_label) + '</span>'
            : '';
        var listedHtml = v.listing_cnt > 0
            ? '<span class="ml-1 text-[10px] text-green-600">&#10003; ' + v.listing_cnt + ' listed</span>'
            : '';
        var btnLabel = inCart ? '&#10003;&nbsp;In&nbsp;list' : '+&nbsp;Add';
        var btnCls   = inCart
            ? 'sp-add-btn flex-shrink-0 whitespace-nowrap text-[11px] font-medium rounded px-2.5 py-1.5 bg-gray-100 text-gray-400 cursor-default'
            : 'sp-add-btn flex-shrink-0 whitespace-nowrap text-[11px] font-medium rounded px-2.5 py-1.5 bg-gray-900 text-white hover:bg-gray-700 transition-colors';

        return '<div class="sp-variant-row flex items-center gap-2 sm:gap-2.5 border border-gray-200 rounded-lg p-2 hover:border-gray-300 transition-colors" data-idx="' + idx + '">' +
            '<img src="' + _esc(v.img) + '" alt="' + _esc(v.set) + '" loading="lazy" ' +
                'class="sp-variant-thumb w-7 sm:w-8 h-10 sm:h-11 object-contain rounded flex-shrink-0 cursor-pointer hover:opacity-75 transition-opacity" ' +
                'data-img="'    + _esc(v.img)             + '" ' +
                'data-img-hd="' + _esc(v.img_hd || v.img) + '" ' +
                'data-idx="'    + idx                     + '">' +
            '<div class="flex-1 min-w-0">' +
                '<div class="text-xs font-medium text-gray-800 truncate">' + _esc(v.set) + foilHtml + '</div>' +
                '<div class="text-xs text-gray-500">' + _esc(v.price) + listedHtml + '</div>' +
            '</div>' +
            '<button class="' + btnCls + '"' +
                (inCart ? ' disabled' : '') +
                ' data-id="'         + _esc(v.id)               + '"' +
                ' data-name="'       + _esc(v.name)             + '"' +
                ' data-set="'        + _esc(v.set)              + '"' +
                ' data-img="'        + _esc(v.img)              + '"' +
                ' data-foil-label="' + _esc(v.foil_label || '') + '">' +
                btnLabel +
            '</button>' +
        '</div>';
    }

    function _spPrev() {
        var cards = Array.from(document.querySelectorAll('.card-option'));
        var idx = _spCardEl ? cards.indexOf(_spCardEl) : -1;
        if (idx <= 0) return;
        _openSellPreview(cards[idx - 1]);
    }

    function _spNext() {
        var cards = Array.from(document.querySelectorAll('.card-option'));
        var idx = _spCardEl ? cards.indexOf(_spCardEl) : -1;
        if (idx < 0 || idx >= cards.length - 1) return;
        _openSellPreview(cards[idx + 1]);
    }

    function _openSellPreview(card) {
        var variants = _parseVariants(card);
        if (!variants.length) return;

        _spCardEl = card;
        _currentVariants = variants;
        _szIdx = 0;

        var nameEl     = document.getElementById('sp-name');
        var rarityEl   = document.getElementById('sp-rarity');
        var imgEl      = document.getElementById('sp-img');
        var variantsEl = document.getElementById('sp-variants');
        var panel      = document.getElementById('sell-preview');
        if (!panel) return;

        if (nameEl)     nameEl.textContent   = variants[0].name;
        if (rarityEl)   rarityEl.textContent = card.dataset.rarity || '';
        if (imgEl)    { imgEl.src = variants[0].img; imgEl.alt = variants[0].name; }
        if (variantsEl) variantsEl.innerHTML = variants.map(_variantRowHTML).join('');

        panel.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        _updateSpInfo(0);
    }

    function _closeSellPreview() {
        var panel = document.getElementById('sell-preview');
        if (panel) panel.classList.add('hidden');
        document.body.style.overflow = '';
    }

    function _updateSpInfo(idx) {
        var v = _currentVariants[idx];
        if (!v) return;

        var selSet    = document.getElementById('sp-sel-set');
        var selPrice  = document.getElementById('sp-sel-price');
        var selFoil   = document.getElementById('sp-sel-foil');
        var selListed = document.getElementById('sp-sel-listed');
        var compEl    = document.getElementById('sp-comparisons');

        if (selSet)   selSet.textContent   = v.set;
        if (selPrice) selPrice.textContent = v.price || '—';
        if (selFoil) {
            if (v.foil_label) { selFoil.textContent = v.foil_label; selFoil.classList.remove('hidden'); }
            else selFoil.classList.add('hidden');
        }
        if (selListed) {
            if (v.listing_cnt > 0) {
                selListed.textContent = v.listing_cnt + (v.listing_cnt === 1 ? ' listed' : ' listed');
                selListed.classList.remove('hidden');
            } else {
                selListed.classList.add('hidden');
            }
        }
        if (!compEl) return;

        var isFoil = !!v.foil_label;
        var comps  = [];

        // Foil/non-foil counterpart in the same set
        for (var i = 0; i < _currentVariants.length; i++) {
            var x = _currentVariants[i];
            if (x.id !== v.id && x.set === v.set && !!x.foil_label !== isFoil) {
                comps.push({ label: x.foil_label || 'Non-foil', sub: '', price: x.price });
                break;
            }
        }

        // Up to 2 other printings from different sets
        var added = 0;
        for (var j = 0; j < _currentVariants.length && added < 2; j++) {
            var y = _currentVariants[j];
            if (y.id !== v.id && y.set !== v.set) {
                comps.push({ label: y.set, sub: y.foil_label || '', price: y.price });
                added++;
            }
        }

        if (comps.length === 0) { compEl.innerHTML = ''; return; }

        var html = '<div class="text-[9px] font-semibold text-gray-400 uppercase tracking-wide mb-1">Also available</div>';
        html += comps.map(function (c) {
            return '<div class="flex justify-between items-start gap-1">' +
                '<div class="min-w-0 leading-snug">' +
                    '<div class="text-[10px] text-gray-600 truncate">' + _esc(c.label) + '</div>' +
                    (c.sub ? '<div class="text-[9px] text-gray-400 truncate">' + _esc(c.sub) + '</div>' : '') +
                '</div>' +
                '<div class="text-[10px] font-semibold text-gray-800 flex-shrink-0 pl-1">' + _esc(c.price || '—') + '</div>' +
            '</div>';
        }).join('');
        compEl.innerHTML = html;
    }

    function _refreshPreviewButtons() {
        document.querySelectorAll('.sp-add-btn').forEach(function (btn) {
            var id = btn.dataset.id;
            if (_cartSet[id]) {
                btn.innerHTML  = '&#10003;&nbsp;In&nbsp;list';
                btn.disabled   = true;
                btn.className  = btn.className
                    .replace('bg-gray-900 text-white hover:bg-gray-700 transition-colors',
                             'bg-gray-100 text-gray-400 cursor-default');
            }
        });
    }

    // ── Sell-zoom (HD full-screen viewer) ──────────────────────────────────────

    function _szShow() {
        _szFlipped = false;
        var v = _currentVariants[_szIdx];
        if (!v) return;
        var img  = document.getElementById('sz-img');
        var name = document.getElementById('sz-name');
        var meta = document.getElementById('sz-meta');
        var ctr  = document.getElementById('sz-counter');
        var flip = document.getElementById('sz-flip');
        if (img)  { img.src = v.img_hd || v.img; img.alt = v.name; }
        if (name) name.textContent = v.name + (v.foil_label ? ' — ' + v.foil_label : '');
        if (meta) meta.textContent = v.set + (v.price ? ' · ' + v.price : '');
        if (ctr)  ctr.textContent  = _currentVariants.length > 1
            ? (_szIdx + 1) + ' / ' + _currentVariants.length : '';
        if (flip) {
            if (v.img_back) { flip.textContent = 'Flip card'; flip.classList.remove('hidden'); }
            else             { flip.classList.add('hidden'); }
        }
    }

    function _szFlip() {
        var v = _currentVariants[_szIdx];
        if (!v || !v.img_back) return;
        _szFlipped = !_szFlipped;
        var img  = document.getElementById('sz-img');
        var flip = document.getElementById('sz-flip');
        if (img)  img.src = _szFlipped ? v.img_back : (v.img_hd || v.img);
        if (flip) flip.textContent = _szFlipped ? 'Show front' : 'Flip card';
    }

    function _openSellZoom(idx) {
        if (!_currentVariants.length) return;
        _szIdx = (idx >= 0 && idx < _currentVariants.length) ? idx : 0;
        _szShow();
        var zoom = document.getElementById('sell-zoom');
        if (zoom) zoom.classList.remove('hidden');
    }

    function _closeSellZoom() {
        var zoom = document.getElementById('sell-zoom');
        if (zoom) zoom.classList.add('hidden');
    }

    function _szPrev() {
        if (_currentVariants.length < 2) return;
        _szIdx = (_szIdx - 1 + _currentVariants.length) % _currentVariants.length;
        _szShow();
        var spImg = document.getElementById('sp-img');
        if (spImg) spImg.src = _currentVariants[_szIdx].img;
        _updateSpInfo(_szIdx);
    }

    function _szNext() {
        if (_currentVariants.length < 2) return;
        _szIdx = (_szIdx + 1) % _currentVariants.length;
        _szShow();
        var spImg = document.getElementById('sp-img');
        if (spImg) spImg.src = _currentVariants[_szIdx].img;
        _updateSpInfo(_szIdx);
    }

    // ── Cart state helpers ─────────────────────────────────────────────────────

    function _addVariant(id, name, set, img, foilLabel) {
        if (_cartSet[id]) { _toast('Already in sell list: ' + name); return; }
        _cart.push({ scryfallId: id, name: name, set: set, img: img, foilLabel: foilLabel || '' });
        _cartSet[id] = true;
        _renderCart();
        _hideCartMessages();
        _saveCart();
        var label = name + (set ? ' (' + set + ')' : '') + (foilLabel ? ' — ' + foilLabel : '');
        _toast('Added: ' + label);
        _refreshPreviewButtons();
    }

    function _removeFromCart(idx) {
        var item = _cart[idx];
        if (item) {
            delete _cartSet[item.scryfallId];
            delete _cartDetails[item.scryfallId];
        }
        _cart.splice(idx, 1);
        _renderCart();
        _hideCartMessages();
        _saveCart();
    }

    // ── Cart rendering ─────────────────────────────────────────────────────────

    var _CONDITIONS = [
        ['M',  'Mint'],
        ['NM', 'Near Mint'],
        ['LP', 'Lightly Played'],
        ['MP', 'Moderately Played'],
        ['HP', 'Heavily Played'],
        ['D',  'Damaged'],
    ];

    function _condOptions(selected) {
        return _CONDITIONS.map(function (c) {
            return '<option value="' + c[0] + '"' + (c[0] === (selected || 'NM') ? ' selected' : '') + '>' + c[1] + '</option>';
        }).join('');
    }

    function _cartRowHTML(item, idx) {
        var d   = _cartDetails[item.scryfallId] || {};
        var img = item.img
            ? '<img src="' + _esc(item.img) + '" alt="' + _esc(item.name) + '" class="w-10 h-14 object-contain rounded shadow-sm flex-shrink-0">'
            : '<div class="w-10 h-14 bg-gray-100 rounded flex-shrink-0"></div>';
        var foilBadge = item.foilLabel
            ? '<span class="ml-1 text-[10px] text-purple-600 font-semibold">' + _esc(item.foilLabel) + '</span>'
            : '';

        return '<div class="cart-item flex gap-2 sm:gap-3 items-start border border-gray-200 rounded-lg p-2 sm:p-3 bg-white" data-idx="' + idx + '">' +
            img +
            '<div class="flex-1 min-w-0">' +
                '<div class="flex items-start justify-between gap-1 mb-2">' +
                    '<div class="min-w-0">' +
                        '<div class="font-medium text-sm truncate">' + _esc(item.name) + foilBadge + '</div>' +
                        '<div class="text-xs text-gray-500 truncate">' + _esc(item.set) + '</div>' +
                    '</div>' +
                    '<button class="remove-item flex-shrink-0 text-gray-300 hover:text-red-500 text-xl leading-none transition-colors" data-idx="' + idx + '" title="Remove">&times;</button>' +
                '</div>' +
                '<div class="grid grid-cols-2 gap-1.5 sm:gap-2 sm:grid-cols-4">' +
                    '<select class="item-condition border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-gray-600">' + _condOptions(d.condition) + '</select>' +
                    '<div>' +
                        '<input type="number" class="item-price w-full border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-gray-600"' +
                            ' placeholder="Price (OMR) *" min="0.001" step="0.001"' +
                            (d.price ? ' value="' + _esc(d.price) + '"' : '') + '>' +
                        '<div class="item-price-err hidden text-[10px] text-red-500 mt-0.5">Price required</div>' +
                    '</div>' +
                    '<input type="number" class="item-qty border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-gray-600"' +
                        ' min="1" placeholder="Qty"' +
                        ' value="' + _esc(d.qty || '1') + '">' +
                    '<input type="text" class="item-notes border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-gray-600"' +
                        ' placeholder="Notes (optional)"' +
                        (d.notes ? ' value="' + _esc(d.notes) + '"' : '') + '>' +
                '</div>' +
            '</div>' +
        '</div>';
    }

    function _renderCart() {
        var section  = document.getElementById('cart-section');
        var itemsEl  = document.getElementById('cart-items');
        var countEl  = document.getElementById('cart-count');
        var pluralEl = document.getElementById('cart-plural');
        if (!section || !itemsEl) return;

        if (_cart.length === 0) { section.classList.add('hidden'); return; }
        section.classList.remove('hidden');
        if (countEl)  countEl.textContent  = _cart.length;
        if (pluralEl) pluralEl.textContent = _cart.length === 1 ? '' : 's';
        // Build rows with saved detail values baked in (no second _restoreCartDetails pass needed)
        itemsEl.innerHTML = _cart.map(_cartRowHTML).join('');
    }

    // ── Submit ─────────────────────────────────────────────────────────────────

    async function _submitAll() {
        var token = localStorage.getItem('mtg_token');
        if (!token) { window.location.href = '/auth/login?next=/sell'; return; }

        _hideCartMessages();

        var rows  = document.querySelectorAll('.cart-item');
        var valid = true;
        rows.forEach(function (row) {
            var inp = row.querySelector('.item-price');
            var err = row.querySelector('.item-price-err');
            var p   = parseFloat(inp ? inp.value : '');
            if (!p || p <= 0) {
                if (inp) { inp.classList.add('border-red-400'); inp.classList.remove('border-gray-300'); }
                if (err) err.classList.remove('hidden');
                valid = false;
            } else {
                if (inp) { inp.classList.remove('border-red-400'); inp.classList.add('border-gray-300'); }
                if (err) err.classList.add('hidden');
            }
        });

        if (!valid) {
            _showCartError('Please set a price greater than 0 for every card before listing.');
            return;
        }

        var btn = document.getElementById('submit-all-btn');
        if (btn) { btn.disabled = true; btn.textContent = 'Listing…'; }

        var errors    = [];
        var succeeded = 0;

        for (var i = 0; i < _cart.length; i++) {
            var item = _cart[i];
            var row  = rows[i];
            if (!row) continue;

            var price     = parseFloat(row.querySelector('.item-price').value);
            var condition = row.querySelector('.item-condition').value;
            var qty       = parseInt(row.querySelector('.item-qty').value, 10) || 1;
            var notes     = (row.querySelector('.item-notes').value || '').trim();

            try {
                var res = await fetch('/api/marketplace/listings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
                    body: JSON.stringify({ scryfall_id: item.scryfallId, condition: condition, price: price, quantity: qty, notes: notes || null }),
                });
                if (res.ok) {
                    succeeded++;
                } else if (res.status === 401) {
                    localStorage.removeItem('mtg_token');
                    window.location.href = '/auth/login?next=/sell';
                    return;
                } else {
                    var d = await res.json();
                    errors.push(item.name + ': ' + (d.detail || 'Failed'));
                }
            } catch (_) {
                errors.push(item.name + ': Network error');
            }
        }

        if (errors.length === 0) {
            _cart = []; _cartSet = {}; _cartDetails = {};
            _clearCartStorage();
            _renderCart();
            var ok = document.getElementById('cart-success');
            if (ok) { ok.textContent = succeeded + ' listing' + (succeeded !== 1 ? 's' : '') + ' created! Redirecting…'; ok.classList.remove('hidden'); }
            setTimeout(function () { window.location.href = '/marketplace'; }, 2000);
        } else {
            var failNames = {};
            errors.forEach(function (e) { failNames[e.split(':')[0]] = true; });
            _cart    = _cart.filter(function (c) { return failNames[c.name]; });
            _cartSet = {};
            _cart.forEach(function (c) { _cartSet[c.scryfallId] = true; });
            _renderCart();
            _saveCart();
            _showCartError((succeeded > 0 ? succeeded + ' listed successfully.\n' : '') + 'Errors:\n' + errors.join('\n'));
            if (btn) { btn.disabled = false; btn.textContent = 'List All Cards for Sale'; }
        }
    }

    // ── DELEGATIONS FIRST ─────────────────────────────────────────────────────

    document.addEventListener('click', function (e) {
        // Sell-zoom: backdrop
        var zoom = document.getElementById('sell-zoom');
        if (zoom && !zoom.classList.contains('hidden') && e.target === zoom) {
            _closeSellZoom(); return;
        }
        if (e.target.closest('#sz-close')) { _closeSellZoom(); return; }
        if (e.target.closest('#sz-prev'))  { _szPrev();        return; }
        if (e.target.closest('#sz-next'))  { _szNext();        return; }
        if (e.target.closest('#sz-flip'))  { _szFlip();        return; }

        // Sell-preview: card navigation arrows
        if (e.target.closest('#sp-prev-card')) { _spPrev(); return; }
        if (e.target.closest('#sp-next-card')) { _spNext(); return; }

        // Sell-preview: main image → open zoom
        if (e.target.closest('#sp-img')) { _openSellZoom(_szIdx); return; }

        // Sell-preview: backdrop
        var panel = document.getElementById('sell-preview');
        if (panel && !panel.classList.contains('hidden') && e.target === panel) {
            _closeSellPreview(); return;
        }
        if (e.target.closest('#sp-close')) { _closeSellPreview(); return; }

        // Sell-preview: add variant
        var spAdd = e.target.closest('.sp-add-btn');
        if (spAdd && !spAdd.disabled) {
            _addVariant(spAdd.dataset.id, spAdd.dataset.name, spAdd.dataset.set, spAdd.dataset.img, spAdd.dataset.foilLabel);
            return;
        }

        // Sell-preview: variant thumbnail → update main image + track idx
        var thumb = e.target.closest('.sp-variant-thumb');
        if (thumb) {
            var spImg = document.getElementById('sp-img');
            if (spImg && thumb.dataset.img) { spImg.src = thumb.dataset.img; }
            var ti = parseInt(thumb.dataset.idx, 10);
            if (!isNaN(ti)) { _szIdx = ti; _updateSpInfo(ti); }
            return;
        }

        // Tile: "+ Add" button
        var tileAdd = e.target.closest('.card-add-btn');
        if (tileAdd) {
            var card = tileAdd.closest('.card-option');
            if (card) {
                var variants = _parseVariants(card);
                if (variants.length === 1) {
                    var v = variants[0];
                    _addVariant(v.id, v.name, v.set, v.img, v.foil_label);
                } else {
                    _openSellPreview(card);
                }
            }
            return;
        }

        // Tile: card click → open preview
        var cardOpt = e.target.closest('.card-option');
        if (cardOpt) { _openSellPreview(cardOpt); return; }

        // Cart: remove
        var rem = e.target.closest('.remove-item');
        if (rem) {
            var idx = parseInt(rem.dataset.idx, 10);
            if (!isNaN(idx)) _removeFromCart(idx);
            return;
        }
    });

    // Hover over a variant row → update info panel (no image change, no state change)
    document.addEventListener('mouseover', function (e) {
        var row = e.target.closest('.sp-variant-row');
        if (!row) return;
        var ri = parseInt(row.dataset.idx, 10);
        if (!isNaN(ri)) _updateSpInfo(ri);
    });

    // Save form values and search query on any input/change event
    document.addEventListener('input',  _handleFormChange);
    document.addEventListener('change', _handleFormChange);

    function _handleFormChange(e) {
        if (e.target.id === 'card-search') {
            try { localStorage.setItem(_SEARCH_KEY, e.target.value || ''); } catch (_) {}
            return;
        }
        var row = e.target.closest('.cart-item');
        if (!row) return;
        _syncCartDetails();
        _saveCart();
    }

    // Keyboard
    document.addEventListener('keydown', function (e) {
        var zoom     = document.getElementById('sell-zoom');
        var zoomOpen = zoom && !zoom.classList.contains('hidden');
        var preview  = document.getElementById('sell-preview');
        var prevOpen = preview && !preview.classList.contains('hidden');

        if (zoomOpen) {
            if (e.key === 'ArrowLeft')              { _szPrev();        return; }
            if (e.key === 'ArrowRight')             { _szNext();        return; }
            if (e.key === 'Escape')                 { _closeSellZoom(); return; }
            if (e.key === 'f' || e.key === 'F')    { _szFlip();        return; }
        }
        if (prevOpen) {
            if (e.key === 'ArrowLeft')  { _spPrev();           return; }
            if (e.key === 'ArrowRight') { _spNext();           return; }
            if (e.key === 'Escape')     { _closeSellPreview(); return; }
        }
    });

    // ── Static controls + auth guard + state restore ───────────────────────────

    function _initControls() {
        if (!localStorage.getItem('mtg_token')) {
            window.location.href = '/auth/login?next=/sell';
            return;
        }

        var submitBtn   = document.getElementById('submit-all-btn');
        var clearAllBtn = document.getElementById('clear-cart-btn');

        if (submitBtn)   submitBtn.addEventListener('click', _submitAll);
        if (clearAllBtn) clearAllBtn.addEventListener('click', function () {
            _cart = []; _cartSet = {}; _cartDetails = {};
            _renderCart();
            _clearCartStorage();
            _hideCartMessages();
        });

        // Restore cart (with form values) and last search query from localStorage
        _loadCart();
        _loadSearch();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _initControls);
    } else {
        _initControls();
    }
})();
