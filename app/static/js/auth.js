(function () {

    // ── Login page ───────────────────────────────────────────────────────────
    var loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            var btn   = document.getElementById('login-btn');
            var errEl = document.getElementById('login-error');
            errEl.classList.add('hidden');
            btn.disabled    = true;
            btn.textContent = 'Logging in...';

            try {
                var res = await fetch('/auth/login', {
                    method:  'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body:    JSON.stringify({
                        email:    loginForm.email.value,
                        password: loginForm.password.value,
                    }),
                });
                if (res.ok) {
                    var data = await res.json();
                    localStorage.setItem('mtg_token', data.access_token);
                    var next = new URLSearchParams(window.location.search).get('next') || '/marketplace';
                    window.location.href = next;
                } else {
                    errEl.textContent = 'Invalid email or password.';
                    errEl.classList.remove('hidden');
                    btn.disabled    = false;
                    btn.textContent = 'Login';
                }
            } catch (_) {
                errEl.textContent = 'Network error. Please try again.';
                errEl.classList.remove('hidden');
                btn.disabled    = false;
                btn.textContent = 'Login';
            }
        });
    }

    // ── Register page ────────────────────────────────────────────────────────
    var registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            var btn   = document.getElementById('register-btn');
            var errEl = document.getElementById('register-error');
            errEl.classList.add('hidden');
            btn.disabled    = true;
            btn.textContent = 'Creating account...';

            try {
                var res = await fetch('/auth/register', {
                    method:  'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body:    JSON.stringify({
                        email:    registerForm.email.value,
                        username: registerForm.username.value,
                        password: registerForm.password.value,
                    }),
                });
                if (res.ok) {
                    // Auto-login after registration
                    var loginRes = await fetch('/auth/login', {
                        method:  'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body:    JSON.stringify({
                            email:    registerForm.email.value,
                            password: registerForm.password.value,
                        }),
                    });
                    if (loginRes.ok) {
                        var loginData = await loginRes.json();
                        localStorage.setItem('mtg_token', loginData.access_token);
                    }
                    window.location.href = '/marketplace';
                } else {
                    var data = await res.json();
                    errEl.textContent = data.detail || 'Registration failed. Please try again.';
                    errEl.classList.remove('hidden');
                    btn.disabled    = false;
                    btn.textContent = 'Create Account';
                }
            } catch (_) {
                errEl.textContent = 'Network error. Please try again.';
                errEl.classList.remove('hidden');
                btn.disabled    = false;
                btn.textContent = 'Create Account';
            }
        });
    }

})();
