(function () {
    // ── Hamburger toggle ──────────────────────────────────────────────────────
    var toggle = document.getElementById('nav-toggle');
    var mobile = document.getElementById('nav-mobile');
    if (toggle && mobile) {
        toggle.addEventListener('click', function () {
            mobile.classList.toggle('hidden');
        });
    }

    // ── Auth state — show/hide links in both desktop + mobile nav ─────────────
    var token = localStorage.getItem('mtg_token');
    if (token) {
        var isAdmin = false;
        try {
            var payload = JSON.parse(atob(token.split('.')[1]));
            isAdmin = payload.role === 'admin';
        } catch (_) {}

        var deskShow = ['nav-my-account', 'nav-collections', 'nav-my-listings'];
        var mobShow  = ['nav-mob-account', 'nav-mob-collections', 'nav-mob-listings'];
        if (isAdmin) { deskShow.push('nav-admin'); mobShow.push('nav-mob-admin'); }

        var desk = { show: deskShow, hide: ['nav-login', 'nav-register'] };
        var mob  = { show: mobShow,  hide: ['nav-mob-login', 'nav-mob-register'] };

        [desk, mob].forEach(function (set) {
            set.show.forEach(function (id) {
                var el = document.getElementById(id);
                if (el) el.classList.remove('hidden');
            });
            set.hide.forEach(function (id) {
                var el = document.getElementById(id);
                if (el) el.classList.add('hidden');
            });
        });
    }
})();
