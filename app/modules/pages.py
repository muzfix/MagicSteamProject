from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func as sqlfunc
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.dependencies import get_current_admin
from app.modules.auth.models import User, UserActivity
from app.modules.marketplace import service as marketplace_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def home_page(request: Request):
    return templates.TemplateResponse(request, "home.html")


@router.get("/auth/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "auth/login.html")


@router.get("/auth/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request, "auth/register.html")


@router.get("/marketplace", response_class=HTMLResponse)
def marketplace_page(request: Request, db: Session = Depends(get_db)):
    total, listings = marketplace_service.get_listings_with_cards(db, listing_type="community")
    return templates.TemplateResponse(request, "marketplace/index.html", {
        "listings": listings,
        "mode": "community",
        "total": total,
    })


@router.get("/store", response_class=HTMLResponse)
def store_page(request: Request, db: Session = Depends(get_db)):
    total, listings = marketplace_service.get_listings_with_cards(db, listing_type="official")
    return templates.TemplateResponse(request, "marketplace/index.html", {
        "listings": listings,
        "mode": "official",
        "total": total,
    })


@router.get("/sell", response_class=HTMLResponse)
def sell_page(request: Request):
    return templates.TemplateResponse(request, "marketplace/create_listing.html")


@router.get("/account", response_class=HTMLResponse)
def account_page(request: Request):
    return templates.TemplateResponse(request, "auth/account.html")


@router.get("/privacy", response_class=HTMLResponse)
def privacy_page(request: Request):
    return templates.TemplateResponse(request, "privacy_policy.html")


@router.get("/admin/activity", response_class=HTMLResponse)
def admin_activity_page(request: Request):
    return templates.TemplateResponse(request, "admin/activity.html")


@router.get("/api/admin/activity")
def admin_activity_data(
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    total_users  = db.query(sqlfunc.count(User.id)).scalar()
    cutoff_30d   = datetime.now(timezone.utc) - timedelta(days=30)
    active_30d   = db.query(sqlfunc.count(sqlfunc.distinct(UserActivity.user_id))).filter(
        UserActivity.created_at >= cutoff_30d
    ).scalar()
    total_logins = db.query(sqlfunc.count(UserActivity.id)).filter(UserActivity.event == "login").scalar()
    total_visits = db.query(sqlfunc.count(UserActivity.id)).filter(UserActivity.event == "visit").scalar()
    total_events = db.query(sqlfunc.count(UserActivity.id)).scalar()

    rows = (
        db.query(UserActivity, User.username)
        .join(User, UserActivity.user_id == User.id)
        .order_by(desc(UserActivity.created_at))
        .limit(limit)
        .offset(offset)
        .all()
    )
    events = [
        {
            "id": a.id,
            "user_id": a.user_id,
            "username": uname,
            "event": a.event,
            "ip_address": a.ip_address or "",
            "country": a.country or "",
            "city": a.city or "",
            "user_agent": a.user_agent or "",
            "created_at": a.created_at.isoformat() if a.created_at else "",
        }
        for a, uname in rows
    ]

    geo_rows = (
        db.query(UserActivity.country, sqlfunc.count(UserActivity.id).label("cnt"))
        .filter(UserActivity.country.isnot(None), UserActivity.country != "")
        .group_by(UserActivity.country)
        .order_by(desc("cnt"))
        .limit(20)
        .all()
    )
    geo = [{"country": r.country, "count": r.cnt} for r in geo_rows]

    return {
        "stats": {
            "total_users": total_users,
            "active_30d": active_30d,
            "total_logins": total_logins,
            "total_visits": total_visits,
        },
        "events": events,
        "geo": geo,
        "total_events": total_events,
    }
