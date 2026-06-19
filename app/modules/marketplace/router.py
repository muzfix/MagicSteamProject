from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.marketplace import service
from app.modules.marketplace.schemas import (
    CodConfirm, ListingCreate, ListingOut, ListingUpdate,
    OrderCreate, OrderOut,
)

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


@router.get("/listings/mine")
def my_listings(
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total, listings = service.get_my_listings(db, current_user.id, limit=limit, offset=offset)
    return {"total": total, "listings": listings}


@router.patch("/listings/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: int,
    data: ListingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return service.update_listing(db, listing_id, current_user.id, data)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/listings/{listing_id}", status_code=204)
def deactivate_listing(
    listing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        service.deactivate_listing(db, listing_id, current_user.id)
    except ValueError as e:
        raise HTTPException(404, str(e))


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


@router.get("/orders/mine")
def my_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.get_my_orders(db, current_user.id)


@router.get("/orders/{order_id}")
def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return service.get_order(db, order_id, current_user.id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/orders/{order_id}/cod", response_model=OrderOut)
def confirm_cod(
    order_id: int,
    data: CodConfirm,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return service.confirm_cod(db, order_id, current_user.id, data.pickup_location)
    except ValueError as e:
        raise HTTPException(400, str(e))
