"""
Gunicorn configuration for MagicSteam.

Usage:
    gunicorn app.main:app -c gunicorn.conf.py

Why CPU × 5 workers?
--------------------
The common formula "2 × CPU + 1" is for CPU-bound work.  MagicSteam uses
synchronous (blocking) SQLAlchemy — every DB query parks the thread in I/O
wait.  The OS can run other threads during that wait, so we over-provision
workers to keep the CPUs busy.  CPU × 5 is the standard multiplier for
I/O-bound blocking frameworks (Gunicorn docs, PGO benchmarks).

Connection pool math:
    24 workers × (pool_size=2 + max_overflow=1) = 72 connections
    PostgreSQL default max_connections = 100 → 28 connections of headroom
    for admin sessions, pg_stat_activity, monitoring, etc.
"""

import multiprocessing

# ── Worker count ──────────────────────────────────────────────────────────────
# CPU × 5 for I/O-bound sync SQLAlchemy.
# Floor at 4 and cap at 24 so a single-core dev machine doesn't spin 5 workers,
# and an 8-core server doesn't exceed the connection-pool budget.
workers = min(max(multiprocessing.cpu_count() * 5, 4), 24)

# UvicornWorker bridges Gunicorn's process model with FastAPI's ASGI interface.
worker_class = "uvicorn.workers.UvicornWorker"

# ── Bind ──────────────────────────────────────────────────────────────────────
# Listen on localhost only; nginx sits in front and handles TLS + rate limiting.
bind = "127.0.0.1:8000"

# ── Timeouts ──────────────────────────────────────────────────────────────────
timeout    = 30     # kill a worker that doesn't respond within 30 s
keepalive  = 5      # keep HTTP/1.1 connections alive for 5 s (matches nginx upstream)
graceful_timeout = 10

# ── Worker recycling ─────────────────────────────────────────────────────────
# SQLAlchemy sessions accumulate memory over many requests; recycle workers
# periodically to prevent slow creep.  Jitter spreads recycling so all 24
# workers don't restart at the same moment.
max_requests        = 1_000
max_requests_jitter = 100

# ── Application preloading ────────────────────────────────────────────────────
# Load the FastAPI app once in the master process before forking workers.
# Workers share the loaded module pages (copy-on-write), which cuts per-worker
# RAM by ~40 MB and makes the startup cache warmup run only once.
preload_app = True

# ── Logging ───────────────────────────────────────────────────────────────────
# stdout/stderr — systemd or Docker picks these up via journald / docker logs.
accesslog = "-"
errorlog  = "-"
loglevel  = "info"
