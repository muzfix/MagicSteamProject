(function () {
    var _token = localStorage.getItem('mtg_token');
    var _colData = null;
    var _isListed = false;
    var _createType = 'collection';
    var _sellCardData = null;
    var _editMode = false;

    function _authH() { return { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _token }; }

    function _esc(s) {
        return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    function _fmtOMR(v) {
        if (v == null || v === 0) return '—';
        if (v >= 1) return v.toFixed(3) + ' OMR';
        var bz = Math.round(v * 1000);
        return bz > 0 ? bz + ' bz' : '—';
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // MODAL DISMISS — Escape key + click outside (shared by index + detail)
    // ═══════════════════════════════════════════════════════════════════════════

    function bindModalDismiss() {
        document.addEventListener('keydown', function (e) {
            if (e.key !== 'Escape') return;
            document.querySelectorAll('.modal-backdrop:not(.hidden)').forEach(function (m) {
                m.classList.add('hidden');
            });
        });
        document.querySelectorAll('.modal-backdrop').forEach(function (backdrop) {
            backdrop.addEventListener('click', function (e) {
                if (e.target === backdrop) backdrop.classList.add('hidden');
            });
        });
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // INDEX PAGE
    // ═══════════════════════════════════════════════════════════════════════════

    function initIndex() {
        if (!_token) { window.location.href = '/auth/login?next=/my-collections'; return; }

        bindModalDismiss();

        // + New button
        var newBtn = document.getElementById('new-collection-btn');
        if (newBtn) newBtn.addEventListener('click', openCreateModal);

        // Modal: type toggle
        var btnColl = document.getElementById('type-collection');
        if (btnColl) btnColl.addEventListener('click', function () { setType('collection'); });
        var btnDeck = document.getElementById('type-deck');
        if (btnDeck) btnDeck.addEventListener('click', function () { setType('deck'); });

        // Modal: create & cancel
        var createBtn = document.getElementById('create-btn');
        if (createBtn) createBtn.addEventListener('click', doCreate);
        var cancelBtn = document.getElementById('cancel-create-btn');
        if (cancelBtn) cancelBtn.addEventListener('click', closeCreateModal);

        // Modal: Enter key in name field
        var nameInput = document.getElementById('new-name');
        if (nameInput) nameInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') doCreate();
        });

        // "Create one" link rendered inside the empty-grid state
        var grid = document.getElementById('collections-grid');
        if (grid) grid.addEventListener('click', function (e) {
            if (e.target.closest('[data-create]')) openCreateModal();
        });

        loadCollections();
    }

    function loadCollections() {
        fetch('/api/collections', { headers: { 'Authorization': 'Bearer ' + _token } })
            .then(function (r) {
                if (r.status === 401) { localStorage.removeItem('mtg_token'); window.location.href = '/auth/login'; return null; }
                return r.json();
            })
            .then(function (cols) { if (cols) renderGrid(cols); })
            .catch(function () {
                var g = document.getElementById('collections-grid');
                if (g) g.innerHTML = '<div class="col-span-full py-8 text-center text-sm text-red-500">Failed to load.</div>';
            });
    }

    function renderGrid(cols) {
        var g = document.getElementById('collections-grid');
        if (!g) return;
        if (!cols.length) {
            g.innerHTML = '<div class="col-span-full py-16 text-center text-sm text-gray-400">' +
                'No collections yet. <button data-create class="underline text-gray-700">Create one</button></div>';
            return;
        }
        g.innerHTML = cols.map(function (c) {
            var coverHtml = c.cover_image_uri
                ? '<img src="' + _esc(c.cover_image_uri) + '" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200" alt="">'
                : '<div class="w-full h-full flex items-center justify-center text-gray-300">' +
                  '<svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                  '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/>' +
                  '</svg></div>';
            var saleBadge = c.is_listed_for_sale
                ? '<div class="absolute top-2 right-2"><span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-green-600 text-white">For Sale</span></div>'
                : '';
            var typeBadge = '<div class="absolute top-2 left-2"><span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-black/50 text-white">' +
                (c.type === 'deck' ? (c.format ? c.format.charAt(0).toUpperCase() + c.format.slice(1) : 'Deck') : 'Collection') + '</span></div>';
            return '<a href="/collections/' + c.id + '" class="group block">' +
                '<div class="aspect-[5/7] bg-gray-100 rounded-lg overflow-hidden shadow-sm group-hover:shadow-md transition-shadow relative">' +
                    coverHtml + typeBadge + saleBadge +
                '</div>' +
                '<div class="mt-2 px-0.5">' +
                    '<div class="font-semibold text-xs leading-tight truncate">' + _esc(c.name) + '</div>' +
                    '<div class="text-[11px] text-gray-400 mt-0.5">' + (c.card_count || 0) + ' cards</div>' +
                    (c.total_value_omr ? '<div class="text-xs font-semibold text-gray-800 mt-0.5">' + _fmtOMR(c.total_value_omr) + '</div>' : '') +
                    (c.is_listed_for_sale && c.bundle_price ? '<div class="text-[11px] text-green-600 mt-0.5">' + c.bundle_price.toFixed(3) + ' OMR listed</div>' : '') +
                '</div>' +
                '</a>';
        }).join('');
    }

    // ── Create modal ─────────────────────────────────────────────────────────

    function openCreateModal() {
        var m = document.getElementById('create-modal');
        if (m) m.classList.remove('hidden');
        setType('collection');
        var ni = document.getElementById('new-name');
        if (ni) { ni.value = ''; ni.focus(); }
        var msg = document.getElementById('create-msg');
        if (msg) msg.classList.add('hidden');
    }

    function closeCreateModal() {
        var m = document.getElementById('create-modal');
        if (m) m.classList.add('hidden');
    }

    function setType(type) {
        _createType = type;
        var btnC = document.getElementById('type-collection');
        var btnD = document.getElementById('type-deck');
        var fs = document.getElementById('format-section');
        var base = 'py-2 text-sm rounded border-2 font-semibold transition-colors ';
        if (btnC) btnC.className = base + (type === 'collection' ? 'border-gray-900 bg-gray-900 text-white' : 'border-gray-200 text-gray-600 hover:border-gray-400');
        if (btnD) btnD.className = base + (type === 'deck' ? 'border-gray-900 bg-gray-900 text-white' : 'border-gray-200 text-gray-600 hover:border-gray-400');
        if (fs) fs.classList.toggle('hidden', type !== 'deck');
    }

    function doCreate() {
        var nameEl = document.getElementById('new-name');
        var name = nameEl ? (nameEl.value || '').trim() : '';
        if (!name) { showCreateMsg('Please enter a name.'); return; }
        var payload = { name: name, type: _createType };
        if (_createType === 'deck') {
            var fmt = document.getElementById('new-format');
            payload.format = fmt ? fmt.value : 'custom';
        }
        var btn = document.getElementById('create-btn');
        if (btn) { btn.disabled = true; btn.textContent = 'Creating…'; }
        fetch('/api/collections', { method: 'POST', headers: _authH(), body: JSON.stringify(payload) })
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
            .then(function (res) {
                if (btn) { btn.disabled = false; btn.textContent = 'Create'; }
                if (res.ok && res.d.id) {
                    window.location.href = '/collections/' + res.d.id;
                } else {
                    showCreateMsg(res.d.detail || 'Failed to create.');
                }
            })
            .catch(function () {
                if (btn) { btn.disabled = false; btn.textContent = 'Create'; }
                showCreateMsg('Network error.');
            });
    }

    function showCreateMsg(text) {
        var el = document.getElementById('create-msg');
        if (!el) return;
        el.textContent = text;
        el.classList.remove('hidden');
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // DETAIL PAGE
    // ═══════════════════════════════════════════════════════════════════════════

    function initDetail() {
        if (!_token) { window.location.href = '/auth/login?next=/collections/' + _COLLECTION_ID; return; }

        bindModalDismiss();

        // Main action buttons (onclick removed — bound here)
        var shareBtn = document.getElementById('share-btn');
        if (shareBtn) shareBtn.addEventListener('click', openShare);
        var sellToggle = document.getElementById('sell-toggle-btn');
        if (sellToggle) sellToggle.addEventListener('click', toggleSaleListing);
        var importBtn = document.getElementById('import-btn');
        if (importBtn) importBtn.addEventListener('click', openImport);

        // Cover art click (cover-wrap has onclick still — keep for simplicity)
        var coverWrap = document.getElementById('cover-wrap');
        if (coverWrap) { coverWrap.removeAttribute('onclick'); coverWrap.addEventListener('click', openCoverPicker); }

        // Edit mode / delete
        var editBtn = document.getElementById('edit-mode-btn');
        if (editBtn) editBtn.addEventListener('click', toggleEditMode);
        var delBtn = document.getElementById('delete-collection-btn');
        if (delBtn) delBtn.addEventListener('click', deleteCollection);

        // Sell-card modal
        var scConfirm = document.getElementById('sell-card-confirm-btn');
        if (scConfirm) scConfirm.addEventListener('click', doSellCard);
        var scCancel = document.getElementById('sell-card-cancel-btn');
        if (scCancel) scCancel.addEventListener('click', closeSellCardModal);

        // Bundle sell modal buttons
        var bsConfirm = document.querySelector('#sell-modal button:first-of-type');
        // Use event delegation on modals instead for robustness
        document.addEventListener('click', function (e) {
            var t = e.target;
            if (t.matches && t.matches('#sell-modal button:not(#sell-card-confirm-btn)')) {
                // handled by onclick still on those buttons
            }
        });

        loadCollection();
        bindPickerClick();
        bindCoverPickerClick();
    }

    function loadCollection() {
        fetch('/api/collections/' + _COLLECTION_ID, { headers: { 'Authorization': 'Bearer ' + _token } })
            .then(function (r) {
                if (r.status === 401) { localStorage.removeItem('mtg_token'); window.location.href = '/auth/login'; return null; }
                if (!r.ok) { var a = document.getElementById('cards-area'); if (a) a.innerHTML = '<div class="py-8 text-center text-sm text-red-500">Collection not found.</div>'; return null; }
                return r.json();
            })
            .then(function (col) {
                if (!col) return;
                _colData = col;
                _isListed = col.is_listed_for_sale;
                renderHeader(col);
                renderCards(col);
                updateSellBtn();
            });
    }

    function renderHeader(col) {
        var nameEl = document.getElementById('col-name');
        if (nameEl) nameEl.textContent = col.name;

        var badge = document.getElementById('col-type-badge');
        if (badge) badge.textContent = col.type === 'deck' ? (col.format || 'Deck') : 'Collection';

        var meta = document.getElementById('col-meta');
        if (meta) {
            var parts = [col.card_count + ' card' + (col.card_count !== 1 ? 's' : '')];
            if (col.type === 'deck' && col.format) {
                var limits = { commander:'100 max', brawl:'60 max', standard:'60+15', modern:'60+15', pioneer:'60+15', legacy:'60+15', vintage:'60+15', pauper:'60+15', custom:'no limit' };
                parts.push(limits[col.format] || col.format);
            }
            meta.innerHTML = parts.join(' &middot; ');
        }

        var val = document.getElementById('col-value');
        if (val && col.total_value_omr) val.textContent = 'Est. value: ' + _fmtOMR(col.total_value_omr);

        if (col.cover_image_uri) {
            var img = document.getElementById('cover-img');
            var ph = document.getElementById('cover-placeholder');
            if (img) { img.src = col.cover_image_uri; img.classList.remove('hidden'); }
            if (ph) ph.classList.add('hidden');
        }

        var catRow = document.getElementById('category-row');
        if (catRow && col.type === 'deck') {
            catRow.classList.remove('hidden');
            var cmdLabel = document.getElementById('commander-radio-label');
            if (cmdLabel && (col.format === 'commander' || col.format === 'brawl')) cmdLabel.classList.remove('hidden');
        }
    }

    function renderCards(col) {
        var area = document.getElementById('cards-area');
        if (!area) return;

        if (!col.cards || !col.cards.length) {
            area.innerHTML = '<div class="py-16 text-center text-sm text-gray-400">No cards yet — use the search above to add cards.</div>';
            return;
        }

        if (col.type === 'deck') {
            var cats = { commander: [], mainboard: [], sideboard: [] };
            col.cards.forEach(function (c) { (cats[c.category] || cats.mainboard).push(c); });
            var html = '';
            var catLabels = { commander: 'Commander', mainboard: 'Mainboard', sideboard: 'Sideboard' };
            ['commander', 'mainboard', 'sideboard'].forEach(function (cat) {
                if (!cats[cat].length) return;
                var total = cats[cat].reduce(function (s, c) { return s + c.quantity; }, 0);
                html += '<div class="mb-8"><h3 class="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3">' +
                    catLabels[cat] + ' (' + total + ')</h3>' +
                    '<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">' +
                    cats[cat].map(cardTileHtml).join('') + '</div></div>';
            });
            area.innerHTML = html;
        } else {
            area.innerHTML = '<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">' +
                col.cards.map(cardTileHtml).join('') + '</div>';
        }

        area.querySelectorAll('.col-remove-btn').forEach(function (btn) {
            btn.addEventListener('click', function (e) { e.stopPropagation(); removeCard(parseInt(btn.dataset.ccid)); });
        });

        area.querySelectorAll('.col-qty-btn').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var ccId = parseInt(btn.dataset.ccid);
                var delta = parseInt(btn.dataset.delta);
                var card = (_colData.cards || []).find(function (c) { return c.id === ccId; });
                if (!card) return;
                updateCardQty(ccId, Math.max(1, card.quantity + delta));
            });
        });

        area.querySelectorAll('.col-sell-btn').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                openSellCardModal({
                    scryfall_id: btn.dataset.scryfallId,
                    name: btn.dataset.name,
                    image_uri: btn.dataset.img,
                    quantity: parseInt(btn.dataset.qty) || 1,
                    set_name: btn.dataset.set,
                });
            });
        });
    }

    function cardTileHtml(c) {
        return '<div class="group relative bg-white rounded-lg overflow-hidden shadow-sm hover:shadow-md transition-shadow border border-gray-100" id="cc-' + c.id + '">' +
            '<div class="aspect-[5/7] bg-gray-50 overflow-hidden relative">' +
                (c.image_uri ? '<img src="' + _esc(c.image_uri) + '" class="w-full h-full object-cover" alt="">' :
                    '<div class="w-full h-full flex items-center justify-center text-gray-200 text-xs">' + _esc(c.name) + '</div>') +
                (c.quantity > 1 ? '<div class="absolute top-1.5 left-1.5 bg-black/70 text-white text-[10px] font-bold px-1.5 py-0.5 rounded">×' + c.quantity + '</div>' : '') +
                '<button class="col-remove-btn absolute top-1.5 right-1.5 w-6 h-6 bg-black/60 hover:bg-red-600 rounded-full text-white text-xs leading-none opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center" data-ccid="' + c.id + '" title="Remove">&times;</button>' +
                '<button class="col-sell-btn absolute bottom-1.5 right-1.5 w-6 h-6 bg-green-600/80 hover:bg-green-600 rounded-full text-white text-[10px] font-bold leading-none opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center" ' +
                'data-scryfall-id="' + _esc(c.scryfall_id) + '" data-name="' + _esc(c.name) + '" data-img="' + _esc(c.image_uri || '') + '" data-qty="' + c.quantity + '" data-set="' + _esc(c.set_name || '') + '" title="Sell this card">$</button>' +
            '</div>' +
            '<div class="p-1.5">' +
                '<div class="font-semibold text-[11px] leading-tight truncate" title="' + _esc(c.name) + '">' + _esc(c.name) + '</div>' +
                '<div class="text-[10px] text-gray-400 truncate">' + _esc(c.set_name) + (c.released_at ? ' (' + c.released_at + ')' : '') + '</div>' +
                '<div class="flex items-center justify-between mt-1">' +
                    '<span class="text-[11px] font-semibold text-gray-700">' + (c.price_omr ? _fmtOMR(c.price_omr) : '—') + '</span>' +
                    '<div class="flex items-center gap-0.5">' +
                        '<button class="col-qty-btn w-4 h-4 text-[10px] text-gray-400 hover:text-gray-700 leading-none" data-ccid="' + c.id + '" data-delta="-1">−</button>' +
                        '<span class="text-[10px] text-gray-600 w-4 text-center">' + c.quantity + '</span>' +
                        '<button class="col-qty-btn w-4 h-4 text-[10px] text-gray-400 hover:text-gray-700 leading-none" data-ccid="' + c.id + '" data-delta="1">+</button>' +
                    '</div>' +
                '</div>' +
            '</div>' +
        '</div>';
    }

    // ── Card picker ──────────────────────────────────────────────────────────

    function bindPickerClick() {
        var results = document.getElementById('col-picker-results');
        if (!results) return;
        results.addEventListener('click', function (e) {
            var tile = e.target.closest('[data-variants]');
            if (!tile) return;
            e.preventDefault(); e.stopPropagation();
            var variants = [];
            try { variants = JSON.parse(tile.dataset.variants || '[]'); } catch (_) {}
            showVariantPopup(tile.dataset.name || (variants[0] && variants[0].name) || 'Card', variants);
        });
    }

    function showVariantPopup(name, variants) {
        var popup = document.getElementById('variant-popup');
        var nameEl = document.getElementById('variant-popup-name');
        var listEl = document.getElementById('variant-list');
        if (!popup || !nameEl || !listEl) return;
        nameEl.textContent = name;
        listEl.innerHTML = variants.map(function (v) {
            var foil = v.foil_label ? ' <span class="text-[10px] text-amber-600">' + _esc(v.foil_label) + '</span>' : '';
            return '<button class="variant-pick-btn w-full text-left flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 transition-colors" data-scryfall-id="' + _esc(v.id) + '">' +
                (v.img ? '<img src="' + _esc(v.img) + '" class="w-8 rounded flex-shrink-0" alt="">' : '<div class="w-8 h-11 bg-gray-100 rounded flex-shrink-0"></div>') +
                '<div class="flex-1 min-w-0"><div class="text-xs font-medium truncate">' + _esc(v.set || '') + foil + '</div>' +
                '<div class="text-[11px] text-gray-400">' + (v.price ? _fmtOMR(v.price) : '—') + '</div></div>' +
                '<div class="text-[10px] font-semibold text-gray-900 bg-gray-100 rounded px-2 py-0.5">Add</div>' +
                '</button>';
        }).join('');
        listEl.querySelectorAll('.variant-pick-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                closeVariantPopup();
                addCard(btn.dataset.scryfallId, getSelectedCategory());
            });
        });
        popup.classList.remove('hidden');
    }

    function closeVariantPopup() {
        var popup = document.getElementById('variant-popup');
        if (popup) popup.classList.add('hidden');
    }

    function getSelectedCategory() {
        var radios = document.querySelectorAll('input[name="add-category"]');
        for (var i = 0; i < radios.length; i++) { if (radios[i].checked) return radios[i].value; }
        return 'mainboard';
    }

    function addCard(scryfallId, category) {
        var badge = document.getElementById('add-mode-badge');
        if (badge) { badge.textContent = 'Adding…'; badge.classList.remove('hidden'); }
        fetch('/api/collections/' + _COLLECTION_ID + '/cards', {
            method: 'POST', headers: _authH(),
            body: JSON.stringify({ scryfall_id: scryfallId, quantity: 1, category: category || 'mainboard' }),
        })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
            if (badge) badge.classList.add('hidden');
            if (res.ok) {
                loadCollection();
                var si = document.getElementById('col-search');
                if (si) si.value = '';
                var pr = document.getElementById('col-picker-results');
                if (pr) pr.innerHTML = '';
            } else {
                if (badge) { badge.textContent = res.d.detail || 'Limit reached'; badge.classList.remove('hidden'); }
                setTimeout(function () { if (badge) badge.classList.add('hidden'); }, 3000);
            }
        })
        .catch(function () { if (badge) badge.classList.add('hidden'); });
    }

    function removeCard(ccId) {
        var tile = document.getElementById('cc-' + ccId);
        if (tile) { tile.style.opacity = '0.3'; tile.style.pointerEvents = 'none'; }
        fetch('/api/collections/' + _COLLECTION_ID + '/cards/' + ccId, { method: 'DELETE', headers: _authH() })
            .then(function (r) {
                if (r.ok || r.status === 204) { loadCollection(); }
                else if (tile) { tile.style.opacity = ''; tile.style.pointerEvents = ''; }
            });
    }

    function updateCardQty(ccId, qty) {
        fetch('/api/collections/' + _COLLECTION_ID + '/cards/' + ccId, {
            method: 'PATCH', headers: _authH(), body: JSON.stringify({ quantity: qty }),
        }).then(function (r) { if (r.ok) loadCollection(); });
    }

    // ── Sell individual card ─────────────────────────────────────────────────

    function openSellCardModal(data) {
        _sellCardData = data;
        var preview = document.getElementById('sell-card-preview');
        if (preview) preview.innerHTML =
            (data.image_uri ? '<img src="' + _esc(data.image_uri) + '" class="w-12 rounded shadow flex-shrink-0" alt="">' : '') +
            '<div><div class="text-sm font-semibold">' + _esc(data.name) + '</div>' +
            '<div class="text-xs text-gray-400">' + _esc(data.set_name || '') + '</div></div>';
        var qtyEl = document.getElementById('sell-card-qty');
        if (qtyEl) qtyEl.value = 1;
        var priceEl = document.getElementById('sell-card-price');
        if (priceEl) priceEl.value = '';
        var msg = document.getElementById('sell-card-msg');
        if (msg) msg.classList.add('hidden');
        var modal = document.getElementById('sell-card-modal');
        if (modal) { modal.classList.remove('hidden'); setTimeout(function () { if (priceEl) priceEl.focus(); }, 50); }
    }

    function closeSellCardModal() {
        var modal = document.getElementById('sell-card-modal');
        if (modal) modal.classList.add('hidden');
        _sellCardData = null;
    }

    function doSellCard() {
        if (!_sellCardData) return;
        var price = parseFloat(document.getElementById('sell-card-price').value);
        var qty = parseInt(document.getElementById('sell-card-qty').value) || 1;
        var condition = document.getElementById('sell-card-condition').value;
        if (!price || price <= 0) { showSellCardMsg('Enter a valid price.'); return; }
        var btn = document.getElementById('sell-card-confirm-btn');
        if (btn) { btn.disabled = true; btn.textContent = 'Listing…'; }
        fetch('/api/marketplace/listings', {
            method: 'POST', headers: _authH(),
            body: JSON.stringify({ scryfall_id: _sellCardData.scryfall_id, condition: condition, price: price, quantity: qty }),
        })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
            if (btn) { btn.disabled = false; btn.textContent = 'List for Sale'; }
            if (res.ok) {
                closeSellCardModal();
                showDetailToast(_sellCardData ? _sellCardData.name : 'Card', 'listed in marketplace');
            } else {
                showSellCardMsg(res.d.detail || 'Failed to list.');
            }
        })
        .catch(function () { if (btn) { btn.disabled = false; btn.textContent = 'List for Sale'; } showSellCardMsg('Network error.'); });
    }

    function showSellCardMsg(text) {
        var el = document.getElementById('sell-card-msg');
        if (!el) return;
        el.textContent = text;
        el.classList.remove('hidden');
    }

    function showDetailToast(name, action) {
        var t = document.createElement('div');
        t.className = 'fixed bottom-4 right-4 z-50 bg-gray-900 text-white text-xs rounded-lg px-4 py-2.5 shadow-lg';
        t.textContent = name + ' ' + action + ' ✓';
        document.body.appendChild(t);
        setTimeout(function () { t.remove(); }, 3000);
    }

    // ── Cover art picker ─────────────────────────────────────────────────────

    function openCoverPicker() {
        var m = document.getElementById('cover-modal');
        if (m) { m.classList.remove('hidden'); setTimeout(function () { var i = document.getElementById('cover-search'); if (i) i.focus(); }, 50); }
    }

    function closeCoverPicker() {
        var m = document.getElementById('cover-modal');
        if (m) m.classList.add('hidden');
    }

    function bindCoverPickerClick() {
        var results = document.getElementById('cover-picker-results');
        if (!results) return;
        results.addEventListener('click', function (e) {
            var tile = e.target.closest('[data-variants]');
            if (!tile) return;
            var variants = [];
            try { variants = JSON.parse(tile.dataset.variants || '[]'); } catch (_) {}
            var img = variants[0] && variants[0].img;
            if (img) setCover(img);
        });
    }

    function setCover(imageUri) {
        fetch('/api/collections/' + _COLLECTION_ID, {
            method: 'PATCH', headers: _authH(), body: JSON.stringify({ cover_image_uri: imageUri }),
        })
        .then(function (r) { return r.json(); })
        .then(function () {
            var img = document.getElementById('cover-img');
            var ph = document.getElementById('cover-placeholder');
            if (img) { img.src = imageUri; img.classList.remove('hidden'); }
            if (ph) ph.classList.add('hidden');
            closeCoverPicker();
        });
    }

    // ── Share / Export ───────────────────────────────────────────────────────

    function openShare() {
        var m = document.getElementById('share-modal');
        if (m) m.classList.remove('hidden');
    }

    function closeShare() {
        var m = document.getElementById('share-modal');
        if (m) m.classList.add('hidden');
    }

    function copyLink() {
        navigator.clipboard.writeText(window.location.href)
            .then(function () { showShareMsg('Link copied!'); })
            .catch(function () { showShareMsg(window.location.href); });
    }

    function doExport(fmt) {
        fetch('/api/collections/' + _COLLECTION_ID + '/export?fmt=' + fmt, { headers: { 'Authorization': 'Bearer ' + _token } })
            .then(function (r) { return r.text(); })
            .then(function (text) {
                var ext = fmt === 'csv' ? '.csv' : '.txt';
                var fileName = (_colData ? _colData.name.replace(/[^a-z0-9]/gi, '_') : 'collection') + ext;
                var blob = new Blob([text], { type: fmt === 'csv' ? 'text/csv' : 'text/plain' });
                var url = URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url; a.download = fileName;
                document.body.appendChild(a); a.click();
                document.body.removeChild(a); URL.revokeObjectURL(url);
                showShareMsg('Exported as ' + fileName);
            })
            .catch(function () { showShareMsg('Export failed.'); });
    }

    function showShareMsg(text) {
        var el = document.getElementById('share-msg');
        if (!el) return;
        el.textContent = text;
        el.classList.remove('hidden');
        setTimeout(function () { el.classList.add('hidden'); }, 3000);
    }

    // ── Edit mode / delete ────────────────────────────────────────────────────

    function toggleEditMode() {
        _editMode = !_editMode;
        var editBtn = document.getElementById('edit-mode-btn');
        var delBtn = document.getElementById('delete-collection-btn');
        if (editBtn) editBtn.textContent = _editMode ? 'Done' : 'Edit';
        if (delBtn) delBtn.classList.toggle('hidden', !_editMode);
    }

    function deleteCollection() {
        var type = _colData ? _colData.type : 'collection';
        var name = _colData ? _colData.name : 'this ' + type;
        if (!confirm('Permanently delete "' + name + '"?\n\nThis removes all cards and cannot be undone.')) return;
        fetch('/api/collections/' + _COLLECTION_ID, { method: 'DELETE', headers: _authH() })
            .then(function (r) {
                if (r.ok || r.status === 204) {
                    window.location.href = '/my-collections';
                } else {
                    alert('Delete failed. Try again.');
                }
            })
            .catch(function () { alert('Network error.'); });
    }

    // ── List entire collection for sale (bundle) ─────────────────────────────

    function updateSellBtn() {
        var btn = document.getElementById('sell-toggle-btn');
        if (!btn) return;
        btn.textContent = _isListed ? 'Remove from Sale' : 'List Collection for Sale';
    }

    function toggleSaleListing() {
        if (_isListed) {
            if (!confirm('Remove this ' + (_colData ? _colData.type : 'collection') + ' from sale?')) return;
            fetch('/api/collections/' + _COLLECTION_ID + '/list-for-sale', { method: 'DELETE', headers: _authH() })
                .then(function (r) { if (r.ok || r.status === 204) { _isListed = false; updateSellBtn(); } });
        } else {
            var m = document.getElementById('sell-modal');
            if (m) m.classList.remove('hidden');
        }
    }

    function closeSellModal() {
        var m = document.getElementById('sell-modal');
        if (m) m.classList.add('hidden');
    }

    function confirmListForSale() {
        var price = parseFloat(document.getElementById('sell-price').value);
        var desc = (document.getElementById('sell-desc').value || '').trim();
        if (!price || price <= 0) { showSellMsg('Enter a valid price.', true); return; }
        fetch('/api/collections/' + _COLLECTION_ID + '/list-for-sale', {
            method: 'POST', headers: _authH(),
            body: JSON.stringify({ price: price, description: desc || null }),
        })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
            if (res.ok) {
                _isListed = true; updateSellBtn(); closeSellModal();
                if (_colData) { _colData.is_listed_for_sale = true; _colData.bundle_price = price; }
            } else { showSellMsg(res.d.detail || 'Failed to list.', true); }
        });
    }

    function showSellMsg(text, isError) {
        var el = document.getElementById('sell-msg');
        if (!el) return;
        el.textContent = text;
        el.className = 'text-xs ' + (isError ? 'text-red-600' : 'text-green-700');
        el.classList.remove('hidden');
    }

    // ── Import ────────────────────────────────────────────────────────────────

    function openImport() {
        var m = document.getElementById('import-modal');
        if (m) m.classList.remove('hidden');
        var r = document.getElementById('import-result');
        if (r) r.classList.add('hidden');
    }

    function closeImport() {
        var m = document.getElementById('import-modal');
        if (m) m.classList.add('hidden');
    }

    function doImport() {
        var textEl = document.getElementById('import-text');
        var text = textEl ? (textEl.value || '').trim() : '';
        if (!text) return;
        var r = document.getElementById('import-result');
        if (r) { r.textContent = 'Importing…'; r.className = 'text-xs p-3 rounded bg-gray-50 text-gray-500'; r.classList.remove('hidden'); }
        fetch('/api/collections/' + _COLLECTION_ID + '/import', {
            method: 'POST', headers: _authH(), body: JSON.stringify({ text: text }),
        })
        .then(function (res) { return res.json(); })
        .then(function (d) {
            var msg = 'Added ' + d.added + ' card' + (d.added !== 1 ? 's' : '') + '.';
            if (d.skipped) msg += ' Skipped ' + d.skipped + '.';
            if (d.errors && d.errors.length) msg += '\n\nErrors:\n' + d.errors.join('\n');
            if (r) { r.textContent = msg; r.className = 'text-xs p-3 rounded whitespace-pre-wrap ' + (d.added > 0 ? 'bg-green-50 text-green-800' : 'bg-amber-50 text-amber-800'); r.classList.remove('hidden'); }
            if (d.added > 0) loadCollection();
        })
        .catch(function () { if (r) { r.textContent = 'Import failed.'; r.classList.remove('hidden'); } });
    }

    // ── Expose on window (for remaining onclick= in detail.html modals) ──────
    window.openCreateModal = openCreateModal;
    window.closeCreateModal = closeCreateModal;
    window.setType = setType;
    window.doCreate = doCreate;
    window.closeVariantPopup = closeVariantPopup;
    window.openCoverPicker = openCoverPicker;
    window.closeCoverPicker = closeCoverPicker;
    window.openShare = openShare;
    window.closeShare = closeShare;
    window.copyLink = copyLink;
    window.doExport = doExport;
    window.toggleSaleListing = toggleSaleListing;
    window.closeSellModal = closeSellModal;
    window.confirmListForSale = confirmListForSale;
    window.openImport = openImport;
    window.closeImport = closeImport;
    window.doImport = doImport;

    // ═══════════════════════════════════════════════════════════════════════════
    // INIT
    // ═══════════════════════════════════════════════════════════════════════════

    function init() {
        if (typeof _COLLECTION_ID !== 'undefined') {
            initDetail();
        } else {
            initIndex();
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
