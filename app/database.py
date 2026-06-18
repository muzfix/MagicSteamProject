from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    # ── SQLite (development) ───────────────────────────────────────────────
    # check_same_thread=False: FastAPI uses a single thread per request but
    # SQLAlchemy's connection pool may hand the same connection to different
    # threads — tell SQLite this is intentional.
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        """Optimise SQLite for a read-heavy concurrent search workload."""
        c = dbapi_conn.cursor()
        # WAL mode: readers never block writers, writers never block readers.
        # Required for any meaningful concurrent load.
        c.execute("PRAGMA journal_mode=WAL")
        # 40 MB in-memory page cache (negative = kilobytes).
        # Hot pages (cards table) stay in RAM → avoids disk I/O on repeated queries.
        c.execute("PRAGMA cache_size=-40960")
        # NORMAL: sync WAL file on checkpoint only (WAL ensures durability).
        # Faster than FULL with no meaningful safety trade-off in WAL mode.
        c.execute("PRAGMA synchronous=NORMAL")
        # Keep temporary tables (sorts, joins) in RAM rather than tmp files.
        c.execute("PRAGMA temp_store=MEMORY")
        # 5-second wait on a locked file rather than returning SQLITE_BUSY immediately.
        c.execute("PRAGMA busy_timeout=5000")
        # 256 MB memory-mapped I/O — OS maps the DB file into virtual address
        # space; reads skip the page-copy step entirely.
        c.execute("PRAGMA mmap_size=268435456")
        # Update query-planner statistics (fast; runs only when stats are stale).
        c.execute("PRAGMA optimize")
        dbapi_conn.commit()

else:
    # ── PostgreSQL (production) ────────────────────────────────────────────
    # Pool sizing: gunicorn.conf.py targets CPU×5 workers (20 on a 4-core box,
    # 24 if you pin to 24 workers for 300 concurrent users).
    # 24 workers × (pool_size=2 + max_overflow=1) = 72 connections — safely
    # under PostgreSQL's default max_connections=100.
    # The old pool_size=3/max_overflow=2 reached exactly 100 (no headroom for
    # admin connections, pg_stat_activity, etc.).
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=2,          # pre-allocated connections per worker
        max_overflow=1,       # burst connections (released after use)
        pool_pre_ping=True,   # discard stale connections before checkout
        pool_recycle=1800,    # recycle idle connections every 30 min
        pool_timeout=30,      # wait max 30 s for a connection before raising
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
