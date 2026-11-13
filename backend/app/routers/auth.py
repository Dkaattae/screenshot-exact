from fastapi import APIRouter, status
from sqlalchemy.exc import IntegrityError

from app.errors import ApiError, unauthorized
from app.models import User
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.security import (
    AppSettings,
    CurrentUser,
    DbSession,
    create_access_token,
    hash_password,
    verify_password,
)
from app.serialize import user_out

router = APIRouter(prefix="/auth", tags=["Auth"])


def _token(user: User, settings: AppSettings) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id, settings), user=user_out(user))


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenOut)
def register(body: RegisterIn, db: DbSession, settings: AppSettings) -> TokenOut:
    email = body.email.lower()
    if db.query(User).filter_by(email=email).first():
        raise ApiError(409, "CONFLICT", "An account with this email already exists.")
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:  # Two sign-ups with one email at the same moment.
        db.rollback()
        raise ApiError(409, "CONFLICT", "An account with this email already exists.") from exc
    return _token(user, settings)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: DbSession, settings: AppSettings) -> TokenOut:
    user = db.query(User).filter_by(email=body.email.lower()).first()
    if not verify_password(body.password, user.password_hash if user else None) or user is None:
        raise unauthorized("Email or password is incorrect.")
    return _token(user, settings)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return user_out(user)
