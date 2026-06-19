from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.collections import service
from app.modules.collections.schemas import (
    BundleListingCreate, CollectionCardAdd, CollectionCardOut,
    CollectionCardUpdate, CollectionCreate, CollectionDetailOut,
    CollectionOut, CollectionUpdate, BundleListingOut, ImportResult,
)

router = APIRouter()


@router.get("", response_model=list[CollectionOut])
def list_collections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.get_user_collections(db, current_user.id)


@router.post("", status_code=201)
def create_collection(
    data: CollectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return service.create_collection(db, current_user.id, data)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{collection_id}")
def get_collection(
    collection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    col = service.get_collection(db, collection_id, current_user.id)
    if not col:
        raise HTTPException(404, "Collection not found")
    return col


@router.patch("/{collection_id}")
def update_collection(
    collection_id: int,
    data: CollectionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return service.update_collection(db, collection_id, current_user.id, data)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/{collection_id}", status_code=204)
def delete_collection(
    collection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        service.delete_collection(db, collection_id, current_user.id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/{collection_id}/cards", status_code=201)
def add_card(
    collection_id: int,
    data: CollectionCardAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return service.add_card(db, collection_id, current_user.id, data)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.patch("/{collection_id}/cards/{collection_card_id}")
def update_card(
    collection_id: int,
    collection_card_id: int,
    data: CollectionCardUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return service.update_card(db, collection_id, current_user.id, collection_card_id, data)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/{collection_id}/cards/{collection_card_id}", status_code=204)
def remove_card(
    collection_id: int,
    collection_card_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        service.remove_card(db, collection_id, current_user.id, collection_card_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/{collection_id}/list-for-sale", status_code=201)
def list_for_sale(
    collection_id: int,
    data: BundleListingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return service.create_bundle_listing(db, collection_id, current_user.id, data)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/{collection_id}/list-for-sale", status_code=204)
def remove_from_sale(
    collection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        service.remove_bundle_listing(db, collection_id, current_user.id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/{collection_id}/export")
def export_collection(
    collection_id: int,
    fmt: str = Query("arena", pattern="^(arena|mtgo|csv)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        text = service.export_collection(db, collection_id, current_user.id, fmt)
        media_type = "text/csv" if fmt == "csv" else "text/plain"
        return PlainTextResponse(text, media_type=media_type)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/{collection_id}/import")
def import_cards(
    collection_id: int,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    text = body.get("text", "")
    if not text:
        raise HTTPException(400, "No text provided")
    try:
        return service.import_cards(db, collection_id, current_user.id, text)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/bundles/all")
def list_bundle_listings(
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    total, bundles = service.get_all_bundle_listings(db, limit=limit, offset=offset)
    return {"total": total, "bundles": bundles}
