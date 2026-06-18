(function () {
    var token = localStorage.getItem('mtg_token');
    if (!token) { window.location.href = '/auth/login?next=/admin/activity'; return; }

    var _offset = 0;
    var _limit  = 100;
    var _total  = 0;

    function _esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function _device(ua) {
        if (!ua) return '—';
        if (/iPhone|iPad|Android|Mobile|webOS|BlackBerry/i.test(ua)) return 'Mobile';
        return 'Desktop';
    }

    function _reltime(iso) {
        if (!iso) return '—';
        var d   = new Date(iso);
        var sec = (Date.now() - d) / 1000;
        if (sec < 60)     return 'just now';
        if (sec < 3600)   return Math.floor(sec / 60) + 'm ago';
        if (sec < 86400)  return Math.floor(sec / 3600) + 'h ago';
        if (sec < 604800) return Math.floor(sec / 86400) + 'd ago';
        return d.toLocaleDateString();
    }

    function _load(off) {
        fetch('/api/admin/activity?limit=' + _limit + '&offset=' + off, {
            headers: { 'Authorization': 'Bearer ' + token },
        })
        .then(function (r) {
            if (r.status === 401) { localStorage.removeItem('mtg_token'); window.location.href = '/auth/login?next=/admin/activity'; return null; }
            if (r.status === 403) {
                document.getElementById('loading-msg').textContent = 'Admin access required.';
                return null;
            }
            return r.json();
        })
        .then(function (data) {
            if (!data) return;
            _total = data.total_events;

            // Stats
            var s = data.stats;
            document.getElementById('stat-users').textContent  = s.total_users;
            document.getElementById('stat-active').textContent = s.active_30d;
            document.getElementById('stat-logins').textContent = s.total_logins;
            document.getElementById('stat-visits').textContent = s.total_visits;
            document.getElementById('event-count').textContent = _total + ' total events';

            // Events table rows
            var tbody = document.getElementById('events-tbody');
            var html  = data.events.map(function (e) {
                var loc  = [e.city, e.country].filter(Boolean).join(', ') || '—';
                var badge = e.event === 'login'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600';
                return '<tr class="border-b border-gray-100 hover:bg-gray-50">' +
                    '<td class="px-3 py-2 text-xs text-gray-400 whitespace-nowrap">' + _esc(_reltime(e.created_at)) + '</td>' +
                    '<td class="px-3 py-2 text-xs font-medium text-gray-800">'       + _esc(e.username)             + '</td>' +
                    '<td class="px-3 py-2"><span class="text-xs px-2 py-0.5 rounded-full font-medium ' + badge + '">' + _esc(e.event) + '</span></td>' +
                    '<td class="px-3 py-2 text-xs text-gray-400 font-mono">'         + _esc(e.ip_address)           + '</td>' +
                    '<td class="px-3 py-2 text-xs text-gray-600">'                   + _esc(loc)                    + '</td>' +
                    '<td class="px-3 py-2 text-xs text-gray-400">'                   + _esc(_device(e.user_agent))  + '</td>' +
                '</tr>';
            }).join('');

            if (off === 0) {
                tbody.innerHTML = html ||
                    '<tr><td colspan="6" class="text-center py-8 text-gray-400 text-sm">No activity recorded yet.</td></tr>';
            } else {
                tbody.innerHTML += html;
            }

            // Load more
            var btn    = document.getElementById('load-more-btn');
            var loaded = off + data.events.length;
            if (loaded < _total) {
                btn.classList.remove('hidden');
                btn.textContent = 'Load more (' + (_total - loaded) + ' remaining)';
                btn.onclick = function () { _load(loaded); };
            } else {
                btn.classList.add('hidden');
            }

            // Geo breakdown
            var geoList = document.getElementById('geo-list');
            if (!data.geo || data.geo.length === 0) {
                geoList.innerHTML = '<p class="text-xs text-gray-400">No location data yet.</p>';
            } else {
                var maxCnt = data.geo[0].count || 1;
                geoList.innerHTML = data.geo.map(function (g) {
                    var pct = Math.max(4, Math.round((g.count / maxCnt) * 100));
                    return '<div class="flex items-center gap-2">' +
                        '<div class="w-20 text-xs text-gray-700 truncate flex-shrink-0">' + _esc(g.country) + '</div>' +
                        '<div class="flex-1 bg-gray-100 rounded-full h-1.5">' +
                            '<div class="bg-blue-500 h-1.5 rounded-full" style="width:' + pct + '%"></div>' +
                        '</div>' +
                        '<div class="text-xs text-gray-400 w-7 text-right flex-shrink-0">' + g.count + '</div>' +
                    '</div>';
                }).join('');
            }

            document.getElementById('loading-msg').classList.add('hidden');
            document.getElementById('activity-content').classList.remove('hidden');
        })
        .catch(function () {
            document.getElementById('loading-msg').textContent = 'Failed to load activity data.';
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { _load(0); });
    } else {
        _load(0);
    }
})();
