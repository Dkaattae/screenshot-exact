"""Email and password sign-in with bearer access tokens (JWT, HS256)."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.errors import forbidden, unauthorized
from app.models import User
from app.storage import LocalStorage

ALGORITHM = "HS256"

_hasher = PasswordHash.recommended()
# Verified against when the email is unknown, so a failed sign-in takes the same time either way.
_DUMMY_HASH = _hasher.hash("not-a-real-password")
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _hasher.verify(password, _DUMMY_HASH)
        return False
    return _hasher.verify(password, password_hash)


def create_access_token(user_id: str, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_storage(request: Request) -> LocalStorage:
    return request.app.state.storage


DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
Storage = Annotated[LocalStorage, Depends(get_storage)]


def current_user(
    db: DbSession,
    settings: AppSettings,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise unauthorized()
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise unauthorized("Your session has expired. Sign in again.") from exc
    except jwt.PyJWTError as exc:
        raise unauthorized() from exc
    user = db.get(User, payload.get("sub"))
    if user is None:
        raise unauthorized()
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def path_user(user_id: str, user: CurrentUser) -> User:
    """The user named in a /users/{user_id}/ path: `me` or the signed-in user's own id."""
    if user_id not in ("me", user.id):
        raise forbidden("You can only access your own data.")
    return user


PathUser = Annotated[User, Depends(path_user)]
