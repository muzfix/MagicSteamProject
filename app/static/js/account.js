(function () {
    var _token = localStorage.getItem('mtg_token');

    if (!_token) {
        window.location.href = '/auth/login?next=/account';
        return;
    }

    function _authHeaders() {
        return { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _token };
    }

    function _showMsg(id, text, isError) {
        var el = document.getElementById(id);
        if (!el) return;
        el.textContent = text;
        el.className = 'text-xs ' + (isError ? 'text-red-600' : 'text-green-700');
        el.classList.remove('hidden');
    }

    function _fmtDate(iso) {
        if (!iso) return 'Never';
        try {
            return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
        } catch (e) { return iso; }
    }

    function _loadMe() {
        fetch('/auth/me', { headers: { 'Authorization': 'Bearer ' + _token } })
            .then(function (r) {
                if (r.status === 401) {
                    localStorage.removeItem('mtg_token');
                    window.location.href = '/auth/login?next=/account';
                    return null;
                }
                return r.json();
            })
            .then(function (u) {
                if (!u) return;

                var emailEl = document.getElementById('acct-email');
                var usernameEl = document.getElementById('acct-username');
                var sinceEl = document.getElementById('acct-since');
                var roleEl = document.getElementById('acct-role');
                var changedEl = document.getElementById('acct-username-changed');
                var badge = document.getElementById('acct-tag-badge');
                var tagInput = document.getElementById('tag-input');
                var cooldownMsg = document.getElementById('username-cooldown-msg');
                var usernameSaveBtn = document.getElementById('username-save-btn');

                if (emailEl) emailEl.textContent = u.email;
                if (usernameEl) usernameEl.textContent = u.username;
                if (sinceEl) sinceEl.textContent = _fmtDate(u.created_at);
                if (roleEl) roleEl.textContent = u.role;
                if (changedEl) changedEl.textContent = _fmtDate(u.username_changed_at);

                if (badge) {
                    if (u.guild_tag) {
                        badge.textContent = u.guild_tag;
                        badge.classList.remove('hidden');
                    } else {
                        badge.classList.add('hidden');
                    }
                }

                if (tagInput) tagInput.value = u.guild_tag || '';

                if (u.username_changed_at && cooldownMsg && usernameSaveBtn) {
                    var yearMs = 365 * 24 * 60 * 60 * 1000;
                    var elapsed = Date.now() - new Date(u.username_changed_at).getTime();
                    if (elapsed < yearMs) {
                        var daysLeft = Math.ceil((yearMs - elapsed) / (24 * 60 * 60 * 1000));
                        cooldownMsg.textContent = 'Last changed on ' + _fmtDate(u.username_changed_at) +
                            '. You can change it again in ' + daysLeft + ' day' + (daysLeft !== 1 ? 's' : '') + '.';
                        cooldownMsg.classList.remove('hidden');
                        usernameSaveBtn.disabled = true;
                    }
                }
            })
            .catch(function () {});
    }

    function _init() {
        var tagSaveBtn = document.getElementById('tag-save-btn');
        var tagClearBtn = document.getElementById('tag-clear-btn');
        var usernameSaveBtn = document.getElementById('username-save-btn');
        var passwordSaveBtn = document.getElementById('password-save-btn');
        var logoutBtn = document.getElementById('logout-btn');

        if (tagSaveBtn) {
            tagSaveBtn.addEventListener('click', function () {
                var tag = (document.getElementById('tag-input').value || '').trim().toUpperCase() || null;
                fetch('/auth/me/guild-tag', {
                    method: 'PATCH',
                    headers: _authHeaders(),
                    body: JSON.stringify({ guild_tag: tag }),
                }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
                .then(function (res) {
                    if (res.ok) {
                        _showMsg('tag-msg', 'Guild tag updated.', false);
                        _loadMe();
                    } else {
                        _showMsg('tag-msg', res.d.detail || 'Failed to update tag.', true);
                    }
                }).catch(function () { _showMsg('tag-msg', 'Network error.', true); });
            });
        }

        if (tagClearBtn) {
            tagClearBtn.addEventListener('click', function () {
                var tagInput = document.getElementById('tag-input');
                if (tagInput) tagInput.value = '';
                fetch('/auth/me/guild-tag', {
                    method: 'PATCH',
                    headers: _authHeaders(),
                    body: JSON.stringify({ guild_tag: null }),
                }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
                .then(function (res) {
                    if (res.ok) {
                        _showMsg('tag-msg', 'Guild tag removed.', false);
                        _loadMe();
                    } else {
                        _showMsg('tag-msg', res.d.detail || 'Failed.', true);
                    }
                }).catch(function () { _showMsg('tag-msg', 'Network error.', true); });
            });
        }

        if (usernameSaveBtn) {
            usernameSaveBtn.addEventListener('click', function () {
                var newUsername = (document.getElementById('new-username-input').value || '').trim();
                var currentPassword = document.getElementById('username-password-input').value || '';
                if (!newUsername || !currentPassword) {
                    _showMsg('username-msg', 'Please fill in all fields.', true);
                    return;
                }
                fetch('/auth/me/username', {
                    method: 'PATCH',
                    headers: _authHeaders(),
                    body: JSON.stringify({ new_username: newUsername, current_password: currentPassword }),
                }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
                .then(function (res) {
                    if (res.ok) {
                        _showMsg('username-msg', 'Username changed successfully.', false);
                        var nui = document.getElementById('new-username-input');
                        var upi = document.getElementById('username-password-input');
                        if (nui) nui.value = '';
                        if (upi) upi.value = '';
                        _loadMe();
                    } else {
                        _showMsg('username-msg', res.d.detail || 'Failed.', true);
                    }
                }).catch(function () { _showMsg('username-msg', 'Network error.', true); });
            });
        }

        if (passwordSaveBtn) {
            passwordSaveBtn.addEventListener('click', function () {
                var current = document.getElementById('current-password-input').value || '';
                var newPw = document.getElementById('new-password-input').value || '';
                var confirm = document.getElementById('confirm-password-input').value || '';
                if (!current || !newPw || !confirm) {
                    _showMsg('password-msg', 'Please fill in all fields.', true);
                    return;
                }
                if (newPw !== confirm) {
                    _showMsg('password-msg', 'New passwords do not match.', true);
                    return;
                }
                if (newPw.length < 8) {
                    _showMsg('password-msg', 'Password must be at least 8 characters.', true);
                    return;
                }
                fetch('/auth/me/password', {
                    method: 'PATCH',
                    headers: _authHeaders(),
                    body: JSON.stringify({ current_password: current, new_password: newPw }),
                }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
                .then(function (res) {
                    if (res.ok) {
                        _showMsg('password-msg', 'Password updated successfully.', false);
                        var cpi = document.getElementById('current-password-input');
                        var npi = document.getElementById('new-password-input');
                        var cfpi = document.getElementById('confirm-password-input');
                        if (cpi) cpi.value = '';
                        if (npi) npi.value = '';
                        if (cfpi) cfpi.value = '';
                    } else {
                        _showMsg('password-msg', res.d.detail || 'Failed.', true);
                    }
                }).catch(function () { _showMsg('password-msg', 'Network error.', true); });
            });
        }

        if (logoutBtn) {
            logoutBtn.addEventListener('click', function () {
                localStorage.removeItem('mtg_token');
                window.location.href = '/';
            });
        }

        _loadMe();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _init);
    } else {
        _init();
    }
})();
