from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status
from sqlalchemy import or_

from app.models import Background
from app.schemas import BackgroundOut
from app.security import AppSettings, DbSession, PathUser, Storage
from app.serialize import background_out
from app.storage import read_image

router = APIRouter(prefix="/users/{user_id}/backgrounds", tags=["Backgrounds"])


@router.get("", response_model=list[BackgroundOut])
def list_backgrounds(user: PathUser, db: DbSession, storage: Storage) -> list[BackgroundOut]:
    backgrounds = (
        db.query(Background)
        .filter(or_(Background.is_preset.is_(True), Background.user_id == user.id))
        .order_by(Background.is_preset.desc(), Background.created_at)
        .all()
    )
    return [background_out(b, storage) for b in backgrounds]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=BackgroundOut)
def upload_background(
    user: PathUser,
    db: DbSession,
    storage: Storage,
    settings: AppSettings,
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form(max_length=200)] = "",
) -> BackgroundOut:
    data, extension = read_image(file, "background", settings.max_upload_bytes)
    background = Background(
        user_id=user.id,
        name=name.strip() or "My background",
        key=storage.input_folder(user.id).save(data, extension, prefix="background-"),
        is_preset=False,
    )
    db.add(background)
    db.commit()
    return background_out(background, storage)
