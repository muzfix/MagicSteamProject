(function () {
    var _token = localStorage.getItem('mtg_token');
    var _colData = null;
    var _isListed = false;
    var _createType = 'collection';
    var _sellCardData = null;
    var _editMode = false;
    var _COLLECTION_ID = null;

    // Picker / card-viewer state
    var _pickerTiles = [];
    var _pickerTileIdx = -1;
    var _currentVariants = [];
    var _selectedVariantIdx = 0;

    function _authH() { return { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _token }; }

    function _esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function _fmtOMR(v) {
        if (v == null || v === 0) return '—';
        if (v >= 1) return v.toFixed(3) + ' OMR';
        var bz = Math.round(v * 1000);
        return bz > 0 ? bz + ' bz' : '—';
    }

    // ── Modal dismiss — Escape + backdrop click ───────────────────────────────

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

    var FORMAT_STYLES = {
        commander: { label: 'EDH',     cls: 'bg-green-100 text-green-700 border-green-200' },
        brawl:     { label: 'Brawl',   cls: 'bg-teal-100 text-teal-700 border-teal-200' },
        standard:  { label: 'STD',     cls: 'bg-blue-100 text-blue-700 border-blue-200' },
        modern:    { label: 'Modern',  cls: 'bg-indigo-100 text-indigo-700 border-indigo-200' },
        pioneer:   { label: 'Pioneer', cls: 'bg-cyan-100 text-cyan-700 border-cyan-200' },
        legacy:    { label: 'Legacy',  cls: 'bg-purple-100 text-purple-700 border-purple-200' },
        vintage:   { label: 'Vintage', cls: 'bg-amber-100 text-amber-700 border-amber-200' },
        pauper:    { label: 'Pauper',  cls: 'bg-gray-100 text-gray-600 border-gray-200' },
        custom:    { label: 'Custom',  cls: 'bg-purple-100 text-purple-700 border-purple-200' },
    };

    function initIndex() {
        if (!_token) { window.location.href = '/auth/login?next=/my-collections'; return; }
        bindModalDismiss();

        var newBtn = document.getElementById('new-collection-btn');
        if (newBtn) newBtn.addEventListener('click', openCreateModal);

        var btnColl = document.getElementById('type-collection');
        if (btnColl) btnColl.addEventListener('click', function () { setType('collection'); });
        var btnDeck = document.getElementById('type-deck');
        if (btnDeck) btnDeck.addEventListener('click', function () { setType('deck'); });

        var createBtn = document.getElementById('create-btn');
        if (createBtn) createBtn.addEventListener('click', doCreate);
        var cancelBtn = document.getElementById('cancel-create-btn');
        if (cancelBtn) cancelBtn.addEventListener('click', closeCreateModal);

        var nameInput = document.getElementById('new-name');
        if (nameInput) nameInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') doCreate(); });

        var grid = document.getElementById('collections-grid');
        if (grid) grid.addEventListener('click', function (e) {
            if (e.target.closest('[data-create]')) openCreateModal();
        });

        // Re-fetch when user navigates back via browser button (bfcache restore)
        window.addEventListener('pageshow', function (e) { if (e.persisted) loadCollections(); });

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
                : '<div class="w-full h-full flex items-center justify-center text-gray-300"><svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg></div>';

            var saleBadge = c.is_listed_for_sale
                ? '<div class="absolute top-2 right-2"><span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-green-600 text-white">For Sale</span></div>'
                : '';
            var overlayBadge = '<div class="absolute top-2 left-2"><span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-black/60 text-white">' +
                (c.type === 'deck' ? 'Deck' : 'Collection') + '</span></div>';

            var fmt = c.type === 'deck' && c.format ? FORMAT_STYLES[c.format] : null;
            var formatBadge = fmt
                ? '<div class="mt-0.5"><span class="inline-block text-[9px] font-bold px-1.5 py-0.5 rounded border leading-none ' + fmt.cls + '">' + _esc(fmt.label) + '</span></div>'
                : '';

            var plural = c.card_count === 1 ? 'card' : 'cards';
            var priceRow = c.total_value_omr
                ? '<div class="text-[11px] text-orange-500 font-semibold mt-0.5">' + _fmtOMR(c.total_value_omr) + '</div>'
                : '';
            var listedRow = (c.is_listed_for_sale && c.bundle_price)
                ? '<div class="text-[10px] text-green-600 mt-0.5">' + c.bundle_price.toFixed(3) + ' OMR listed</div>'
                : '';

            return '<a href="/collections/' + c.id + '" class="group block">' +
                '<div class="aspect-[5/7] bg-gray-100 rounded-lg overflow-hidden shadow-sm group-hover:shadow-md transition-shadow relative">' +
                    coverHtml + overlayBadge + saleBadge +
                '</div>' +
                '<div class="mt-2 px-0.5">' +
                    '<div class="font-semibold text-xs leading-tight truncate">' + _esc(c.name) + '</div>' +
                    formatBadge +
                    '<div class="text-[11px] text-gray-400 mt-0.5">' + (c.card_count || 0) + ' ' + plural + '</div>' +
                    priceRow + listedRow +
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
                if (res.ok && res.d.id) { window.location.href = '/collections/' + res.d.id; }
                else { showCreateMsg(res.d.detail || 'Failed to create.'); }
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

        var shareBtn = document.getElementById('share-btn');
        if (shareBtn) shareBtn.addEventListener('click', openShare);
        var sellToggle = document.getElementById('sell-toggle-btn');
        if (sellToggle) sellToggle.addEventListener('click', toggleSaleListing);
        var importBtn = document.getElementById('import-btn');
        if (importBtn) importBtn.addEventListener('click', openImport);
        var coverWrap = document.getElementById('cover-wrap');
        if (coverWrap) { coverWrap.removeAttribute('onclick'); coverWrap.addEventListener('click', openCoverPicker); }
        var editBtn = document.getElementById('edit-mode-btn');
        if (editBtn) editBtn.addEventListener('click', toggleEditMode);
        var delBtn = document.getElementById('delete-collection-btn');
        if (delBtn) delBtn.addEventListener('click', deleteCollection);
        var scConfirm = document.getElementById('sell-card-confirm-btn');
        if (scConfirm) scConfirm.addEventListener('click', doSellCard);
        var scCancel = document.getElementById('sell-card-cancel-btn');
        if (scCancel) scCancel.addEventListener('click', closeSellCardModal);

        bindVariantPopup();
        loadCollection();
        bindPickerClick();
        bindCoverPickerClick();
    }

    function loadCollection() {
        fetch('/api/collections/' + _COLLECTION_ID, { headers: { 'Authorization': 'Bearer ' + _token } })
            .then(function (r) {
                if (r.status === 401) { localStorage.removeItem('mtg_token'); window.location.href = '/auth/login'; return null; }
                if (!r.ok) {
                    var a = document.getElementById('cards-area');
                    if (a) a.innerHTML = '<div class="py-8 text-center text-sm text-red-500">Could not load — is the server running?</div>';
                    return null;
                }
                return r.json();
            })
            .then(function (col) {
                if (!col) return;
                _colData = col;
                _isListed = col.is_listed_for_sale;
                renderHeader(col);
                renderCards(col);
                renderStats(col);
                updateSellBtn();
            })
            .catch(function (err) {
                var a = document.getElementById('cards-area');
                if (a) a.innerHTML = '<div class="py-8 text-center text-sm text-red-500">Network error.<br><code class="text-xs">' + _esc(err && err.message ? err.message : String(err)) + '</code></div>';
            });
    }

    function renderHeader(col) {
        var nameEl = document.getElementById('col-name');
        if (nameEl) nameEl.textContent = col.name;

        var badge = document.getElementById('col-type-badge');
        if (badge) {
            if (col.type === 'deck' && col.format && FORMAT_STYLES[col.format]) {
                badge.textContent = FORMAT_STYLES[col.format].label;
            } else {
                badge.textContent = col.type === 'deck' ? 'Deck' : 'Collection';
            }
        }

        var meta = document.getElementById('col-meta');
        if (meta) {
            var plural = col.card_count !== 1 ? 's' : '';
            var parts = [col.card_count + ' card' + plural];
            if (col.type === 'deck' && col.format) {
                var limits = { commander: '100 max', brawl: '60 max', standard: '60+15', modern: '60+15', pioneer: '60+15', legacy: '60+15', vintage: '60+15', pauper: '60+15', custom: 'no limit' };
                parts.push(limits[col.format] || col.format);
            }
            meta.innerHTML = parts.join(' &middot; ');
        }

        var val = document.getElementById('col-value');
        if (val) val.textContent = col.total_value_omr ? 'Est. value: ' + _fmtOMR(col.total_value_omr) : '';

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
                openSellCardModal({ scryfall_id: btn.dataset.scryfallId, name: btn.dataset.name, image_uri: btn.dataset.img, quantity: parseInt(btn.dataset.qty) || 1, set_name: btn.dataset.set });
            });
        });
    }

    function cardTileHtml(c) {
        var setLine = _esc(c.set_name || '') + (c.released_at ? ' (' + _esc(c.released_at) + ')' : '');
        return '<div class="group relative bg-white rounded-lg overflow-hidden shadow-sm hover:shadow-md transition-shadow border border-gray-100" id="cc-' + c.id + '">' +
            '<div class="aspect-[5/7] bg-gray-50 overflow-hidden relative">' +
                (c.image_uri ? '<img src="' + _esc(c.image_uri) + '" class="w-full h-full ' + ((c.layout === 'planar' || c.layout === 'scheme' || c.layout === 'art_series' || c.layout === 'vanguard') ? 'object-contain' : 'object-cover') + '" alt="">' :
                    '<div class="w-full h-full flex items-center justify-center text-gray-200 text-xs p-1 text-center">' + _esc(c.name) + '</div>') +
                (c.quantity > 1 ? '<div class="absolute top-1.5 left-1.5 bg-black/70 text-white text-[10px] font-bold px-1.5 py-0.5 rounded">×' + c.quantity + '</div>' : '') +
                '<button class="col-remove-btn absolute top-1.5 right-1.5 w-6 h-6 bg-black/60 hover:bg-red-600 rounded-full text-white text-xs leading-none opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center" data-ccid="' + c.id + '" title="Remove">&times;</button>' +
                '<button class="col-sell-btn absolute bottom-1.5 right-1.5 w-6 h-6 bg-green-600/80 hover:bg-green-600 rounded-full text-white text-[10px] font-bold leading-none opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center" ' +
                'data-scryfall-id="' + _esc(c.scryfall_id) + '" data-name="' + _esc(c.name) + '" data-img="' + _esc(c.image_uri || '') + '" data-qty="' + c.quantity + '" data-set="' + _esc(c.set_name || '') + '" title="Sell this card">$</button>' +
            '</div>' +
            '<div class="p-1.5">' +
                '<div class="font-semibold text-[11px] leading-tight truncate" title="' + _esc(c.name) + '">' + _esc(c.name) + '</div>' +
                '<div class="text-[10px] text-gray-400 truncate leading-tight">' + setLine + '</div>' +
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

    // ── Stats panel ──────────────────────────────────────────────────────────

    var _FORMAT_LIMITS = { commander: 100, brawl: 60, standard: 60, modern: 60, pioneer: 60, legacy: 60, vintage: 60, pauper: 60 };

    var _TYPE_META = [
        { key: 'Land',         cls: 'bg-amber-100 text-amber-800',    needle: 'Land' },
        { key: 'Creature',     cls: 'bg-green-100 text-green-800',    needle: 'Creature' },
        { key: 'Instant',      cls: 'bg-blue-100 text-blue-800',      needle: 'Instant' },
        { key: 'Sorcery',      cls: 'bg-indigo-100 text-indigo-800',  needle: 'Sorcery' },
        { key: 'Artifact',     cls: 'bg-gray-200 text-gray-700',      needle: 'Artifact' },
        { key: 'Enchantment',  cls: 'bg-teal-100 text-teal-700',      needle: 'Enchantment' },
        { key: 'Planeswalker', cls: 'bg-orange-100 text-orange-800',  needle: 'Planeswalker' },
        { key: 'Battle',       cls: 'bg-red-100 text-red-800',        needle: 'Battle' },
        { key: 'Other',        cls: 'bg-gray-100 text-gray-600',      needle: null },
    ];

    function renderStats(col) {
        var el = document.getElementById('deck-stats');
        if (!el) return;
        var cards = col.cards || [];
        if (!cards.length) { el.classList.add('hidden'); return; }

        var totalQty = col.card_count;
        var limit = col.type === 'deck' ? (_FORMAT_LIMITS[col.format] || null) : null;
        var totalValue = cards.reduce(function (s, c) { return s + (c.price_omr || 0) * c.quantity; }, 0);

        // Type breakdown — commander slot excluded, priority-first matching
        var typeCounts = {};
        _TYPE_META.forEach(function (t) { typeCounts[t.key] = 0; });
        var nonCmdrTotal = 0;
        var hasTypeData = false;
        cards.forEach(function (c) {
            if (c.category === 'commander') return;
            var q = c.quantity;
            nonCmdrTotal += q;
            var tl = c.type_line || '';
            if (tl) hasTypeData = true;
            var matched = false;
            for (var i = 0; i < _TYPE_META.length - 1; i++) {
                if (tl.indexOf(_TYPE_META[i].needle) >= 0) { typeCounts[_TYPE_META[i].key] += q; matched = true; break; }
            }
            if (!matched) typeCounts['Other'] += q;
        });

        // Mana curve (non-land, non-commander)
        var curve = {};
        var hasCurve = false;
        cards.forEach(function (c) {
            if (c.category === 'commander') return;
            if (c.type_line && c.type_line.indexOf('Land') >= 0) return;
            if (c.cmc == null) return;
            hasCurve = true;
            var key = c.cmc >= 7 ? '7+' : String(Math.floor(c.cmc));
            curve[key] = (curve[key] || 0) + c.quantity;
        });

        var countHtml = limit
            ? '<span class="font-bold text-gray-900">' + totalQty + '</span><span class="text-gray-400"> / ' + limit + ' cards</span>'
            : '<span class="font-bold text-gray-900">' + totalQty + '</span><span class="text-gray-400"> card' + (totalQty !== 1 ? 's' : '') + '</span>';
        var valueHtml = totalValue > 0.001
            ? '<span class="text-gray-300 mx-2">|</span><span class="text-orange-500 font-semibold">' + _fmtOMR(totalValue) + '</span>'
            : '';

        var typeHtml = '';
        if (hasTypeData) {
            typeHtml = '<div class="mt-2 flex flex-wrap gap-1">' +
                _TYPE_META.filter(function (t) { return typeCounts[t.key] > 0; }).map(function (t) {
                    var pct = nonCmdrTotal > 0 ? Math.round(typeCounts[t.key] / nonCmdrTotal * 100) : 0;
                    return '<span class="inline-flex items-center gap-0.5 text-[10px] font-medium px-1.5 py-0.5 rounded ' + t.cls + '">' +
                        _esc(t.key) + ' ' + typeCounts[t.key] +
                        ' <span class="opacity-60">(' + pct + '%)</span></span>';
                }).join('') + '</div>';
        }

        var curveHtml = '';
        if (hasCurve) {
            var curveKeys = ['0', '1', '2', '3', '4', '5', '6', '7+'];
            var maxBar = curveKeys.reduce(function (m, k) { return Math.max(m, curve[k] || 0); }, 0);
            if (maxBar > 0) {
                curveHtml = '<div class="mt-3"><div class="text-[9px] font-bold uppercase tracking-widest text-gray-400 mb-1.5">Mana curve (non-land)</div>' +
                    '<div class="flex items-end gap-1 h-12">' +
                    curveKeys.map(function (k) {
                        var v = curve[k] || 0;
                        var barH = maxBar > 0 ? Math.round(v / maxBar * 32) : 0;
                        if (v > 0 && barH < 3) barH = 3;
                        return '<div class="flex flex-col items-center" style="min-width:20px">' +
                            '<div class="text-[8px] text-gray-500 leading-none mb-0.5">' + (v > 0 ? v : '') + '</div>' +
                            '<div class="w-full rounded-t" style="height:' + barH + 'px;background:' + (v > 0 ? '#6366f1' : 'transparent') + '"></div>' +
                            '<div class="text-[8px] text-gray-400 leading-none mt-0.5">' + k + '</div>' +
                        '</div>';
                    }).join('') +
                    '</div></div>';
            }
        }

        el.innerHTML = '<div class="flex flex-wrap items-baseline gap-x-0.5 text-sm">' + countHtml + valueHtml + '</div>' + typeHtml + curveHtml;
        el.classList.remove('hidden');
    }

    // ── Card picker / viewer ──────────────────────────────────────────────────

    function _isPartnerEligible(card) {
        var oracle = (card.oracle_text || '').toLowerCase();
        var tl = (card.type_line || '').toLowerCase();
        return (
            oracle.indexOf('partner') >= 0 ||
            oracle.indexOf('choose a background') >= 0 ||
            oracle.indexOf('friends forever') >= 0 ||
            oracle.indexOf("doctor's companion") >= 0 ||
            (tl.indexOf('background') >= 0 && tl.indexOf('enchantment') >= 0)
        );
    }

    function bindPickerClick() {
        var results = document.getElementById('col-picker-results');
        if (!results) return;
        results.addEventListener('click', function (e) {
            var tile = e.target.closest('[data-variants]');
            if (!tile) return;
            e.preventDefault();
            e.stopPropagation();  // prevent lightbox.js from also opening
            _pickerTiles = Array.from(results.querySelectorAll('[data-variants]'));
            _pickerTileIdx = _pickerTiles.indexOf(tile);
            _selectedVariantIdx = 0;
            try { _currentVariants = JSON.parse(tile.dataset.variants || '[]'); } catch (_) { _currentVariants = []; }
            _openPickerViewer();
        });
    }

    function _openPickerViewer() {
        var tile = _pickerTiles[_pickerTileIdx];
        if (!tile) return;
        var name = tile.dataset.name || (_currentVariants[0] && _currentVariants[0].name) || 'Card';
        showVariantPopup(name);
    }

    function navPickerCard(delta) {
        if (_pickerTiles.length < 2) return;
        _pickerTileIdx = (_pickerTileIdx + delta + _pickerTiles.length) % _pickerTiles.length;
        _selectedVariantIdx = 0;
        var tile = _pickerTiles[_pickerTileIdx];
        if (!tile) return;
        try { _currentVariants = JSON.parse(tile.dataset.variants || '[]'); } catch (_) { _currentVariants = []; }
        _openPickerViewer();
    }
    window.navPickerCard = navPickerCard;

    function showVariantPopup(name) {
        var popup = document.getElementById('variant-popup');
        var nameEl = document.getElementById('variant-popup-name');
        var counterEl = document.getElementById('variant-popup-counter');
        var listEl = document.getElementById('variant-list');
        var previewImg = document.getElementById('variant-preview-img');
        if (!popup) return;

        if (nameEl) nameEl.textContent = name;
        if (counterEl) counterEl.textContent = _pickerTiles.length > 1 ? (_pickerTileIdx + 1) + ' / ' + _pickerTiles.length : '';

        var selV = _currentVariants[_selectedVariantIdx] || _currentVariants[0];
        if (previewImg) { previewImg.src = selV ? (selV.img_hd || selV.img || '') : ''; previewImg.alt = name; }
        _updatePickerPreviewInfo(selV, name);

        if (listEl) {
            listEl.innerHTML = _currentVariants.length
                ? _currentVariants.map(function (v, i) {
                    var foil = v.foil_label ? '<span class="text-[9px] text-amber-600 font-semibold ml-1">' + _esc(v.foil_label) + '</span>' : '';
                    var isSel = i === _selectedVariantIdx;
                    return '<div class="variant-row flex items-center gap-2.5 px-3 py-2.5 cursor-pointer transition-colors ' + (isSel ? 'bg-blue-50' : 'hover:bg-gray-50') + '" data-vidx="' + i + '">' +
                        (v.img ? '<img src="' + _esc(v.img) + '" class="w-8 rounded flex-shrink-0 shadow-sm" alt="">' : '<div class="w-8 h-11 bg-gray-100 rounded flex-shrink-0"></div>') +
                        '<div class="flex-1 min-w-0">' +
                            '<div class="text-xs font-medium leading-tight">' + _esc(v.set || '') + foil + '</div>' +
                            (v.released_at ? '<div class="text-[11px] text-gray-400 leading-tight">' + _esc(v.released_at) + '</div>' : '') +
                        '</div>' +
                        '<div class="text-[11px] text-gray-500 flex-shrink-0 mr-1">' + (v.price != null ? _fmtOMR(v.price) : '—') + '</div>' +
                        '<button class="variant-add-btn flex-shrink-0 text-[11px] font-bold bg-gray-900 text-white rounded px-2.5 py-1 hover:bg-gray-700 transition-colors whitespace-nowrap" data-scryfall-id="' + _esc(v.id || '') + '">Add</button>' +
                    '</div>';
                }).join('')
                : '<div class="px-3 py-6 text-center text-sm text-gray-400">No printings available</div>';
        }

        popup.classList.remove('hidden');
    }

    function bindVariantPopup() {
        var listEl = document.getElementById('variant-list');
        var previewImg = document.getElementById('variant-preview-img');

        if (listEl) {
            listEl.addEventListener('click', function (e) {
                var addBtn = e.target.closest('.variant-add-btn');
                if (addBtn) {
                    e.stopPropagation();
                    var sid = addBtn.dataset.scryfallId;
                    if (sid) { closeVariantPopup(); addCard(sid, getSelectedCategory()); }
                    return;
                }
                var row = e.target.closest('.variant-row');
                if (row) {
                    var vi = parseInt(row.dataset.vidx, 10);
                    if (isNaN(vi)) return;
                    _selectedVariantIdx = vi;
                    var v = _currentVariants[vi];
                    if (previewImg && v) previewImg.src = v.img_hd || v.img || '';
                    _updatePickerPreviewInfo(v, null);
                    // update highlight
                    listEl.querySelectorAll('.variant-row').forEach(function (r, ri) {
                        var s = ri === vi;
                        if (s) { r.classList.add('bg-blue-50'); r.classList.remove('hover:bg-gray-50'); }
                        else  { r.classList.remove('bg-blue-50'); r.classList.add('hover:bg-gray-50'); }
                    });
                }
            });
        }

        var closeBtn = document.getElementById('variant-close-btn');
        if (closeBtn) closeBtn.addEventListener('click', closeVariantPopup);

        var prevBtn = document.getElementById('picker-prev-btn');
        if (prevBtn) prevBtn.addEventListener('click', function () { navPickerCard(-1); });
        var nextBtn = document.getElementById('picker-next-btn');
        if (nextBtn) nextBtn.addEventListener('click', function () { navPickerCard(1); });

        // Zoom button on the HD preview thumbnail
        var zoomBtn = document.getElementById('variant-preview-zoom-btn');
        if (zoomBtn) zoomBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            var v = _currentVariants[_selectedVariantIdx] || _currentVariants[0];
            if (v) _openPickerZoom(v);
        });

        // Zoom overlay controls
        var pz      = document.getElementById('picker-zoom');
        var pzClose = document.getElementById('pz-close');
        var pzPrev  = document.getElementById('pz-prev');
        var pzNext  = document.getElementById('pz-next');
        var pzFlip  = document.getElementById('pz-flip');
        var pzImg   = document.getElementById('pz-img');
        if (pzClose) pzClose.addEventListener('click', _closePickerZoom);
        if (pzImg)   pzImg.addEventListener('click',   _closePickerZoom);
        if (pz)      pz.addEventListener('click', function (e) { if (e.target === pz) _closePickerZoom(); });
        if (pzPrev)  pzPrev.addEventListener('click', function (e) { e.stopPropagation(); _navPickerZoomVariant(-1); });
        if (pzNext)  pzNext.addEventListener('click', function (e) { e.stopPropagation(); _navPickerZoomVariant(1); });
        if (pzFlip)  pzFlip.addEventListener('click', function (e) { e.stopPropagation(); _pzFlip(); });

        // Keyboard: zoom gets priority; then popup card navigation
        document.addEventListener('keydown', function (e) {
            var pz2 = document.getElementById('picker-zoom');
            if (pz2 && !pz2.classList.contains('hidden')) {
                if (e.key === 'ArrowLeft')               { e.preventDefault(); _navPickerZoomVariant(-1); }
                if (e.key === 'ArrowRight')              { e.preventDefault(); _navPickerZoomVariant(1); }
                if (e.key === 'f' || e.key === 'F')      { e.preventDefault(); _pzFlip(); }
                if (e.key === 'Escape')                  { e.preventDefault(); _closePickerZoom(); }
                return;
            }
            var popup = document.getElementById('variant-popup');
            if (!popup || popup.classList.contains('hidden')) return;
            if (e.key === 'ArrowLeft')  { e.preventDefault(); navPickerCard(-1); }
            if (e.key === 'ArrowRight') { e.preventDefault(); navPickerCard(1); }
        });
    }

    function closeVariantPopup() {
        var popup = document.getElementById('variant-popup');
        if (popup) popup.classList.add('hidden');
        _closePickerZoom();
    }

    // ── Picker preview info ───────────────────────────────────────────────────
    function _updatePickerPreviewInfo(v, fallbackName) {
        var nameEl  = document.getElementById('variant-preview-name');
        var setEl   = document.getElementById('variant-preview-set');
        var priceEl = document.getElementById('variant-preview-price');
        if (!v) {
            if (nameEl)  nameEl.textContent  = fallbackName || '';
            if (setEl)   setEl.textContent   = '';
            if (priceEl) priceEl.textContent = '';
            return;
        }
        if (nameEl)  nameEl.textContent  = v.name || fallbackName || '';
        if (setEl)   setEl.textContent   = v.set ? (v.set + (v.released_at ? ' (' + v.released_at + ')' : '')) : '';
        if (priceEl) priceEl.textContent = v.price != null ? _fmtOMR(v.price) : '—';
    }

    // ── Picker zoom overlay ───────────────────────────────────────────────────
    var _pzCurrentBack = '';
    var _pzCurrentImg  = '';
    var _pzFlipped     = false;

    function _openPickerZoom(v) {
        var pz = document.getElementById('picker-zoom');
        if (!pz || !v) return;
        _pzCurrentImg  = v.img_hd || v.img || '';
        _pzCurrentBack = v.img_back || '';
        _pzFlipped     = false;

        var isLandscape = (v.layout === 'planar' || v.layout === 'scheme' || v.layout === 'art_series' || v.layout === 'vanguard');
        var img = document.getElementById('pz-img');
        if (img) {
            img.className = 'object-contain rounded-xl shadow-2xl cursor-zoom-out ' +
                (isLandscape ? 'max-h-[70vh] max-w-[min(900px,92vw)]' : 'max-h-[78vh] max-w-[min(480px,90vw)]');
            img.src = _pzCurrentImg;
            img.alt = v.name || '';
        }
        var nameEl  = document.getElementById('pz-name');
        var setEl   = document.getElementById('pz-set');
        var priceEl = document.getElementById('pz-price');
        var counter = document.getElementById('pz-counter');
        var flip    = document.getElementById('pz-flip');
        if (nameEl)  nameEl.textContent  = v.name || '';
        if (setEl)   setEl.textContent   = v.set ? (v.set + (v.released_at ? ' (' + v.released_at + ')' : '')) : '';
        if (priceEl) priceEl.textContent = v.price != null ? _fmtOMR(v.price) : '—';
        if (counter) counter.textContent = _currentVariants.length > 1
            ? (_selectedVariantIdx + 1) + ' / ' + _currentVariants.length : '';
        if (flip) {
            if (_pzCurrentBack) { flip.textContent = 'Flip card'; flip.classList.remove('hidden'); }
            else flip.classList.add('hidden');
        }
        pz.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }

    function _closePickerZoom() {
        var pz = document.getElementById('picker-zoom');
        if (pz) pz.classList.add('hidden');
        document.body.style.overflow = '';
    }

    function _navPickerZoomVariant(delta) {
        if (_currentVariants.length < 2) return;
        _selectedVariantIdx = (_selectedVariantIdx + delta + _currentVariants.length) % _currentVariants.length;
        var v = _currentVariants[_selectedVariantIdx];
        // sync variant list highlight
        var listEl = document.getElementById('variant-list');
        if (listEl) {
            listEl.querySelectorAll('.variant-row').forEach(function (r, ri) {
                if (ri === _selectedVariantIdx) { r.classList.add('bg-blue-50'); r.classList.remove('hover:bg-gray-50'); }
                else { r.classList.remove('bg-blue-50'); r.classList.add('hover:bg-gray-50'); }
            });
        }
        // sync thumbnail + info in underlying popup
        var previewImg = document.getElementById('variant-preview-img');
        if (previewImg && v) previewImg.src = v.img_hd || v.img || '';
        _updatePickerPreviewInfo(v, null);
        // re-open zoom with new variant
        _openPickerZoom(v);
    }

    function _pzFlip() {
        if (!_pzCurrentBack) return;
        _pzFlipped = !_pzFlipped;
        var img  = document.getElementById('pz-img');
        var flip = document.getElementById('pz-flip');
        if (img)  img.src         = _pzFlipped ? _pzCurrentBack : _pzCurrentImg;
        if (flip) flip.textContent = _pzFlipped ? 'Show front' : 'Flip card';
    }

    function getSelectedCategory() {
        var radios = document.querySelectorAll('input[name="add-category"]');
        for (var i = 0; i < radios.length; i++) { if (radios[i].checked) return radios[i].value; }
        return 'mainboard';
    }

    function addCard(scryfallId, category) {
        // Client-side guard for commander slot
        if (category === 'commander' && _colData) {
            var cmds = (_colData.cards || []).filter(function (c) { return c.category === 'commander'; });
            if (cmds.length >= 2) { showAddBadge('Commander slot full (max 2 with Partner)'); return; }
            if (cmds.length === 1 && !_isPartnerEligible(cmds[0])) {
                showAddBadge('Current commander doesn\'t support a partner');
                return;
            }
        }

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
                // Immediate cover update for commander (backend also sets it, full reload will confirm)
                if (category === 'commander' && res.d && res.d.image_uri) {
                    var img = document.getElementById('cover-img');
                    var ph = document.getElementById('cover-placeholder');
                    if (img) { img.src = res.d.image_uri; img.classList.remove('hidden'); }
                    if (ph) ph.classList.add('hidden');
                }
                loadCollection();
                var si = document.getElementById('col-search');
                if (si) si.value = '';
                var pr = document.getElementById('col-picker-results');
                if (pr) pr.innerHTML = '';
            } else {
                showAddBadge(res.d.detail || 'Limit reached');
            }
        })
        .catch(function () { if (badge) badge.classList.add('hidden'); });
    }

    function showAddBadge(text) {
        var badge = document.getElementById('add-mode-badge');
        if (!badge) return;
        badge.textContent = text;
        badge.classList.remove('hidden');
        setTimeout(function () { badge.classList.add('hidden'); }, 3500);
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
            '<div><div class="text-sm font-semibold">' + _esc(data.name) + '</div><div class="text-xs text-gray-400">' + _esc(data.set_name || '') + '</div></div>';
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
            if (res.ok) { closeSellCardModal(); showDetailToast(_sellCardData ? _sellCardData.name : 'Card', 'listed in marketplace'); }
            else { showSellCardMsg(res.d.detail || 'Failed to list.'); }
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

    // ── Share / Export ────────────────────────────────────────────────────────

    function openShare() { var m = document.getElementById('share-modal'); if (m) m.classList.remove('hidden'); }
    function closeShare() { var m = document.getElementById('share-modal'); if (m) m.classList.add('hidden'); }

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
                var a = document.createElement('a'); a.href = url; a.download = fileName;
                document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url);
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
                if (r.ok || r.status === 204) { window.location.href = '/my-collections'; }
                else { alert('Delete failed. Try again.'); }
            })
            .catch(function () { alert('Network error.'); });
    }

    // ── Bundle sale ───────────────────────────────────────────────────────────

    function updateSellBtn() {
        var btn = document.getElementById('sell-toggle-btn');
        if (!btn) return;
        var noun = (_colData && _colData.type === 'deck') ? 'Deck' : 'Collection';
        btn.textContent = _isListed ? 'Remove from Sale' : 'List ' + noun + ' for Sale';
    }

    function toggleSaleListing() {
        if (_isListed) {
            if (!confirm('Remove this ' + (_colData ? _colData.type : 'collection') + ' from sale?')) return;
            fetch('/api/collections/' + _COLLECTION_ID + '/list-for-sale', { method: 'DELETE', headers: _authH() })
                .then(function (r) { if (r.ok || r.status === 204) { _isListed = false; updateSellBtn(); } });
        } else {
            var m = document.getElementById('sell-modal');
            if (m) m.classList.remove('hidden');
            // Pre-fill asking price with the deck's estimated card value
            var totalOmr = _colData && _colData.total_value_omr;
            var priceInput = document.getElementById('sell-price');
            if (priceInput) priceInput.value = totalOmr ? totalOmr.toFixed(3) : '';
            var hint = document.getElementById('sell-value-hint');
            if (hint) {
                if (totalOmr) {
                    hint.textContent = 'Estimated card value: ' + _fmtOMR(totalOmr);
                    hint.classList.remove('hidden');
                } else {
                    hint.classList.add('hidden');
                }
            }
            var sellMsg = document.getElementById('sell-msg');
            if (sellMsg) sellMsg.classList.add('hidden');
            setTimeout(function () { if (priceInput) priceInput.focus(); }, 50);
        }
    }

    function closeSellModal() { var m = document.getElementById('sell-modal'); if (m) m.classList.add('hidden'); }

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

    function closeImport() { var m = document.getElementById('import-modal'); if (m) m.classList.add('hidden'); }

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

    // ── Window exports (for remaining onclick= in modal buttons) ─────────────
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
    // INIT — script at bottom of <body>, no defer needed; DOM is complete
    // ═══════════════════════════════════════════════════════════════════════════

    (function init() {
        var area = document.getElementById('cards-area');
        if (area && area.dataset.collectionId) {
            _COLLECTION_ID = parseInt(area.dataset.collectionId, 10);
            initDetail();
        } else {
            initIndex();
        }
    })();
})();
