from datetime import datetime, timezone

_visit_cache: dict[int, datetime] = {}
_VISIT_THROTTLE_SECONDS = 3600  # log at most once per hour per user


def _get_client_ip(request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


def _resolve_geo(ip: str) -> tuple[str, str]:
    """Resolve country/city from IP. Returns ('Local','') for private IPs,
    ('','') if GeoLite2 database is not installed."""
    import ipaddress, os
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback:
            return "Local", ""
    except ValueError:
        return "", ""
    try:
        import geoip2.database
        db_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "../../data/GeoLite2-City.mmdb")
        )
        if os.path.exists(db_path):
            with geoip2.database.Reader(db_path) as reader:
                r = reader.city(ip)
                return r.country.name or "", r.city.name or ""
    except Exception:
        pass
    return "", ""


def log_event(user_id: int, event: str, request) -> None:
    """Write one activity row using its own DB session. Never raises."""
    try:
        from app.database import SessionLocal
        from app.modules.auth.models import UserActivity
        ip = _get_client_ip(request)
        country, city = _resolve_geo(ip)
        ua = (request.headers.get("user-agent") or "")[:256]
        db = SessionLocal()
        try:
            db.add(UserActivity(
                user_id=user_id,
                event=event,
                ip_address=ip,
                country=country,
                city=city,
                user_agent=ua,
            ))
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


def log_visit(user_id: int, request) -> None:
    """Throttled visit log — fires at most once per hour per user."""
    now = datetime.now(timezone.utc)
    last = _visit_cache.get(user_id)
    if last and (now - last).total_seconds() < _VISIT_THROTTLE_SECONDS:
        return
    _visit_cache[user_id] = now
    log_event(user_id, "visit", request)
