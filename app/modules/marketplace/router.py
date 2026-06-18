from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.marketplace import service
from app.modules.marketplace.schemas import ListingCreate, ListingOut, OrderCreate, OrderOut

router = APIRouter()


@router.get("/listings")
def list_listings(
    mode: str = Query("community", pattern="^(official|community)$"),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    total, listings = service.get_listings(db, listing_type=mode, limit=limit, offset=offset)
    return {"total": total, "listings": [ListingOut.model_validate(l) for l in listings]}


@router.post("/listings", response_model=ListingOut, status_code=201)
def create_listing(
    data: ListingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return service.create_listing(db, user_id=current_user.id, user_role=current_user.role, data=data)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/orders", response_model=OrderOut, status_code=201)
def create_order(
    data: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return service.create_order(db, buyer_id=current_user.id, data=data)
    except ValueError as e:
        raise HTTPException(404, str(e))
