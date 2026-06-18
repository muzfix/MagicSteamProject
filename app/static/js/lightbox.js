(function () {
    var _cards = [], _idx = 0, _flipped = false;
    var _lbCurrentImg = '', _lbCurrentBack = '';
    var _vExpanded = false;
    var _VERSIONS_PREVIEW = 5;  // rule of 5: show first 5, collapse the rest

    function _esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // ── Public API ────────────────────────────────────────────────────────────
    window.openLightbox = function (el) {
        var selector = el.classList.contains('browse-card') ? '.browse-card' : '.card-option';
        var all = Array.from(document.querySelectorAll(selector));
        _cards = all.map(function (e) {
            var variants = [];
            try { variants = JSON.parse(e.dataset.variants || '[]'); } catch (_) {}
            return {
                name:     e.dataset.name   || '',
                set:      e.dataset.set    || '',
                img:      e.dataset.image  || '',
                back:     e.dataset.back   || '',
                layout:   e.dataset.layout || 'normal',
                price:    e.dataset.price  || '',
                variants: variants,
            };
        });
        _idx = all.indexOf(el);
        if (_idx < 0) _idx = 0;
        _lbShow();
        document.getElementById('lb').classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    };

    function _lbClose() {
        document.getElementById('lb').classList.add('hidden');
        document.body.style.overflow = '';
    }

    function _lbPrev() {
        if (_cards.length < 2) return;
        _idx = (_idx - 1 + _cards.length) % _cards.length;
        _lbShow();
    }

    function _lbNext() {
        if (_cards.length < 2) return;
        _idx = (_idx + 1) % _cards.length;
        _lbShow();
    }

    // Flip uses _lbCurrentBack so it works for both the representative image
    // and any variant selected from the versions list.
    function _lbFlip() {
        if (!_lbCurrentBack) return;
        _flipped = !_flipped;
        document.getElementById('lb-img').src = _flipped ? _lbCurrentBack : _lbCurrentImg;
        document.getElementById('lb-flip').textContent = _flipped ? 'Show front' : 'Flip card';
    }

    // Called when a row in the versions list is clicked.
    function _lbSelectVariant(vi) {
        var c = _cards[_idx];
        var v = c && c.variants && c.variants[vi];
        if (!v) return;
        _lbCurrentImg  = v.img_hd || v.img;
        _lbCurrentBack = v.img_back || '';
        _flipped = false;
        var img   = document.getElementById('lb-img');
        var setEl = document.getElementById('lb-set');
        var prEl  = document.getElementById('lb-price');
        var flip  = document.getElementById('lb-flip');
        if (img)   { img.src = _lbCurrentImg; img.alt = v.name; }
        if (setEl)   setEl.textContent = v.set;
        if (prEl)    prEl.textContent  = v.price || '—';
        if (flip) {
            if (_lbCurrentBack) { flip.textContent = 'Flip card'; flip.classList.remove('hidden'); }
            else                   flip.classList.add('hidden');
        }
    }

    // Render the collapsible versions list for the current card.
    function _renderVersions() {
        var panel  = document.getElementById('lb-versions');
        var list   = document.getElementById('lb-versions-list');
        var toggle = document.getElementById('lb-versions-toggle');
        if (!panel || !list || !toggle) return;

        var c        = _cards[_idx];
        var variants = (c && c.variants) || [];

        if (variants.length <= 1) { panel.classList.add('hidden'); return; }
        panel.classList.remove('hidden');

        var shown = _vExpanded ? variants : variants.slice(0, _VERSIONS_PREVIEW);
        list.innerHTML = shown.map(function (v, i) {
            var foilHtml = v.foil_label
                ? ' <span class="text-purple-300 text-[10px] ml-0.5">' + _esc(v.foil_label) + '</span>'
                : '';
            return (
                '<div class="lb-ver-row flex items-center gap-2 px-3 py-2 hover:bg-white/10 cursor-pointer transition-colors" data-vidx="' + i + '">' +
                    '<div class="flex-1 min-w-0 text-white/80 text-[11px] truncate">' + _esc(v.set) + foilHtml + '</div>' +
                    '<div class="text-green-400 font-semibold text-[11px] flex-shrink-0">' + _esc(v.price || '—') + '</div>' +
                '</div>'
            );
        }).join('');

        var remaining = variants.length - _VERSIONS_PREVIEW;
        if (!_vExpanded && remaining > 0) {
            toggle.textContent = 'Show ' + remaining + ' more versions ▼';
            toggle.classList.remove('hidden');
        } else if (_vExpanded && variants.length > _VERSIONS_PREVIEW) {
            toggle.textContent = 'Show fewer ▲';
            toggle.classList.remove('hidden');
        } else {
            toggle.classList.add('hidden');
        }
    }

    function _lbShow() {
        _flipped   = false;
        _vExpanded = false;
        var c = _cards[_idx];
        if (!c) return;

        // Use HD image from the first variant if available (picker tiles carry variants JSON).
        // Browse/marketplace tiles don't have variants, so fall back to the tile's data-image.
        var v0 = c.variants && c.variants[0];
        _lbCurrentImg  = (v0 && (v0.img_hd || v0.img)) || c.img;
        _lbCurrentBack = (v0 && v0.img_back) || c.back || '';

        var img = document.getElementById('lb-img');
        img.src = _lbCurrentImg;
        img.alt = c.name;
        document.getElementById('lb-name').textContent  = c.name;
        document.getElementById('lb-set').textContent   = c.set;
        document.getElementById('lb-price').textContent = c.price;
        document.getElementById('lb-counter').textContent =
            _cards.length > 1 ? (_idx + 1) + ' / ' + _cards.length : '';
        var flip = document.getElementById('lb-flip');
        if (_lbCurrentBack) {
            flip.textContent = 'Flip card';
            flip.classList.remove('hidden');
        } else {
            flip.classList.add('hidden');
        }
        _renderVersions();
    }

    // ── Hide sell-only buttons on non-sell pages ──────────────────────────────
    function _hideSellButtons() {
        if (document.getElementById('sell-preview')) return;
        document.querySelectorAll('.card-add-btn').forEach(function (b) {
            b.style.display = 'none';
        });
    }

    // ── Delegations ───────────────────────────────────────────────────────────
    document.addEventListener('click', function (e) {
        // Clicks inside the lightbox are handled by lb / lbInner direct listeners
        if (e.target.closest('#lb')) return;
        var card = e.target.closest('.browse-card');
        // On non-sell pages (homepage, browse) .card-option tiles open the lightbox
        if (!card && !document.getElementById('sell-preview')) {
            card = e.target.closest('.card-option');
        }
        if (card) window.openLightbox(card);
    });

    document.addEventListener('keydown', function (e) {
        var lb = document.getElementById('lb');
        if (!lb || lb.classList.contains('hidden')) return;
        if (e.key === 'ArrowLeft')  { e.preventDefault(); _lbPrev(); }
        if (e.key === 'ArrowRight') { e.preventDefault(); _lbNext(); }
        if (e.key === 'Escape')     { _lbClose(); }
        if ((e.key === 'f' || e.key === 'F') && _lbCurrentBack) _lbFlip();
    });

    // Hide sell buttons in picker results loaded after initial page paint
    document.addEventListener('htmx:afterSwap', _hideSellButtons);

    // ── Wire lightbox controls ─────────────────────────────────────────────────
    function _initControls() {
        var lb      = document.getElementById('lb');
        var lbInner = document.getElementById('lb-inner');
        var lbPrev  = document.getElementById('lb-prev');
        var lbNext  = document.getElementById('lb-next');
        var lbFlip  = document.getElementById('lb-flip');
        if (!lb || !lbInner || !lbPrev || !lbNext || !lbFlip) return;

        lb.addEventListener('click', _lbClose);

        // stopPropagation prevents clicks inside the inner panel from closing
        // the lightbox via the backdrop handler. We also handle dynamic elements
        // (version rows, toggle) here since they're injected via innerHTML.
        lbInner.addEventListener('click', function (e) {
            e.stopPropagation();
            var row = e.target.closest('.lb-ver-row');
            if (row) { _lbSelectVariant(parseInt(row.dataset.vidx, 10)); return; }
            if (e.target.closest('#lb-versions-toggle')) { _vExpanded = !_vExpanded; _renderVersions(); }
        });

        lbPrev.addEventListener('click', function (e) { e.stopPropagation(); _lbPrev(); });
        lbNext.addEventListener('click', function (e) { e.stopPropagation(); _lbNext(); });
        lbFlip.addEventListener('click', function (e) { e.stopPropagation(); _lbFlip(); });

        _hideSellButtons();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _initControls);
    } else {
        _initControls();
    }
})();
