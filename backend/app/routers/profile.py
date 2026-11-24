from typing import Annotated

from fastapi import APIRouter, File, Form, Response, UploadFile, status

from app.errors import validation_error
from app.models import BodyProfile, DefaultBody, utcnow
from app.routers import parse_measurements
from app.schemas import BodyProfileOut, DefaultBodyOut, ProfileOut
from app.security import AppSettings, DbSession, PathUser, Storage
from app.serialize import body_out, default_body_out
from app.storage import read_image

router = APIRouter(tags=["Profile"])


@router.get("/users/{user_id}/profile", response_model=ProfileOut)
def get_profile(user: PathUser, db: DbSession, storage: Storage) -> ProfileOut:
    profile = db.query(BodyProfile).filter_by(user_id=user.id).one_or_none()
    return ProfileOut(body=body_out(profile, storage) if profile else None)


@router.put("/users/{user_id}/body", response_model=BodyProfileOut)
def save_body(
    user: PathUser,
    db: DbSession,
    storage: Storage,
    settings: AppSettings,
    front: Annotated[UploadFile, File()],
    side: Annotated[UploadFile, File()],
    back: Annotated[UploadFile, File()],
    consent: Annotated[str, Form()],
    height_cm: Annotated[float | None, Form(gt=0, lt=300)] = None,
    measurements: Annotated[str | None, Form()] = None,
) -> BodyProfileOut:
    if consent != "true":
        raise validation_error("Your consent is required to save body photos.")
    parsed = parse_measurements(measurements)
    images = {
        view: read_image(upload, view, settings.max_upload_bytes)
        for view, upload in (("front", front), ("side", side), ("back", back))
    }
    folder = storage.input_folder(user.id)
    keys = {view: folder.save(data, ext, prefix="body-") for view, (data, ext) in images.items()}

    profile = db.query(BodyProfile).filter_by(user_id=user.id).one_or_none()
    old_keys = (profile.front_key, profile.side_key, profile.back_key) if profile else ()
    if profile is None:
        profile = BodyProfile(user_id=user.id)
        db.add(profile)
    now = utcnow()
    profile.front_key, profile.side_key, profile.back_key = (
        keys["front"],
        keys["side"],
        keys["back"],
    )
    profile.height_cm = height_cm
    profile.measurements = parsed
    profile.consent_at = now
    profile.updated_at = now
    db.commit()
    storage.delete(*old_keys)
    return body_out(profile, storage)


@router.delete("/users/{user_id}/body", status_code=status.HTTP_204_NO_CONTENT)
def delete_body(user: PathUser, db: DbSession, storage: Storage) -> Response:
    profile = db.query(BodyProfile).filter_by(user_id=user.id).one_or_none()
    if profile is not None:
        keys = (profile.front_key, profile.side_key, profile.back_key)
        db.delete(profile)
        db.commit()
        storage.delete(*keys)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/bodies/defaults", response_model=list[DefaultBodyOut])
def list_default_bodies(db: DbSession, storage: Storage) -> list[DefaultBodyOut]:
    bodies = db.query(DefaultBody).order_by(DefaultBody.name).all()
    return [default_body_out(body, storage) for body in bodies]
