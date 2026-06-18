from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.modules.auth.models import User
from app.modules.auth.schemas import UserRegister

_YEAR = timedelta(days=365)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload["exp"] = expire
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def register_user(db: Session, data: UserRegister) -> User:
    user = User(
        email=data.email,
        username=data.username,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def change_username(db: Session, user: User, new_username: str, current_password: str) -> User:
    if not verify_password(current_password, user.password_hash):
        raise ValueError("Current password is incorrect")

    # Enforce one-change-per-year cooldown
    if user.username_changed_at is not None:
        last = user.username_changed_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        elapsed = datetime.now(timezone.utc) - last
        if elapsed < _YEAR:
            days_left = (_YEAR - elapsed).days + 1
            raise ValueError(
                f"Username can only be changed once per year. "
                f"You can change it again in {days_left} day{'s' if days_left != 1 else ''}."
            )

    if new_username == user.username:
        raise ValueError("New username must be different from your current username")

    taken = db.query(User).filter(User.username == new_username, User.id != user.id).first()
    if taken:
        raise ValueError("That username is already taken")

    user.username = new_username
    user.username_changed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, current_password: str, new_password: str) -> User:
    if not verify_password(current_password, user.password_hash):
        raise ValueError("Current password is incorrect")
    user.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(user)
    return user
