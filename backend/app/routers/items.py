from typing import Annotated

from fastapi import APIRouter, File, Form, Response, UploadFile, status

from app.errors import not_found, validation_error
from app.models import Item, User
from app.routers import parse_measurements
from app.schemas import ItemOut, ItemPatch, Slot
from app.security import AppSettings, DbSession, PathUser, Storage
from app.serialize import item_out
from app.storage import has_file, read_image

router = APIRouter(prefix="/users/{user_id}/items", tags=["Wardrobe"])


def _get_item(db: DbSession, user: User, item_id: str) -> Item:
    item = db.get(Item, item_id)
    if item is None or item.user_id != user.id:
        raise not_found("Item")
    return item


@router.get("", response_model=list[ItemOut])
def list_items(
    user: PathUser, db: DbSession, storage: Storage, slot: Slot | None = None
) -> list[ItemOut]:
    query = db.query(Item).filter_by(user_id=user.id)
    if slot:
        query = query.filter_by(slot=slot)
    return [item_out(item, storage) for item in query.order_by(Item.created_at).all()]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ItemOut)
def create_item(
    user: PathUser,
    db: DbSession,
    storage: Storage,
    settings: AppSettings,
    front: Annotated[UploadFile, File()],
    slot: Annotated[Slot, Form()],
    name: Annotated[str, Form(max_length=200)],
    back: Annotated[UploadFile | None, File()] = None,
    measurements: Annotated[str | None, Form()] = None,
) -> ItemOut:
    if not name.strip():
        raise validation_error("Give the item a name.")
    parsed = parse_measurements(measurements)
    front_data, front_ext = read_image(front, "front", settings.max_upload_bytes)
    back_image = read_image(back, "back", settings.max_upload_bytes) if has_file(back) else None
    item = Item(
        user_id=user.id,
        slot=slot,
        name=name.strip(),
        front_key=storage.save(front_data, front_ext, prefix="item-"),
        back_key=storage.save(*back_image, prefix="item-") if back_image else None,
        measurements=parsed,
    )
    db.add(item)
    db.commit()
    return item_out(item, storage)


@router.patch("/{item_id}", response_model=ItemOut)
def update_item(
    item_id: str, body: ItemPatch, user: PathUser, db: DbSession, storage: Storage
) -> ItemOut:
    item = _get_item(db, user, item_id)
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes:
        if not changes["name"].strip():
            raise validation_error("Give the item a name.")
        item.name = changes["name"].strip()
    if "slot" in changes:
        item.slot = changes["slot"]
    if "measurements" in changes:
        item.measurements = changes["measurements"]
    db.commit()
    return item_out(item, storage)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: str, user: PathUser, db: DbSession, storage: Storage) -> Response:
    item = _get_item(db, user, item_id)
    keys = (item.front_key, item.back_key)
    db.delete(item)
    db.commit()
    storage.delete(*keys)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
