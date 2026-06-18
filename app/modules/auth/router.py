from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import limiter
from app.modules.auth import service
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.auth.profanity import is_valid_tag
from app.modules.auth.schemas import (
    GuildTagUpdate, PasswordUpdate, Token,
    UserLogin, UserOut, UserRegister, UsernameUpdate,
)

router = APIRouter()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, data: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    return service.register_user(db, data)


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(request: Request, data: UserLogin, db: Session = Depends(get_db)):
    user = service.authenticate_user(db, data.email, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = service.create_access_token({"sub": str(user.id), "role": user.role})
    from app.modules.auth.activity import log_event
    log_event(user.id, "login", request)
    return {"access_token": token}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me/guild-tag", response_model=UserOut)
def set_guild_tag(
    data: GuildTagUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tag = (data.guild_tag or "").strip().upper() or None
    if tag:
        ok, reason = is_valid_tag(tag)
        if not ok:
            raise HTTPException(status_code=400, detail=reason)
    current_user.guild_tag = tag
    db.commit()
    db.refresh(current_user)
    return current_user


@router.patch("/me/username", response_model=UserOut)
def change_username(
    data: UsernameUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return service.change_username(db, current_user, data.new_username, data.current_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/me/password")
def change_password(
    data: PasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        service.change_password(db, current_user, data.current_password, data.new_password)
        return {"detail": "Password updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
