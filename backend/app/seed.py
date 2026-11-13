"""Seed data every user sees: 2 default bodies and 3 preset backgrounds."""

from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Background, DefaultBody
from app.storage import LocalStorage

ASSETS = Path(__file__).parent / "seed_assets"

PRESET_BACKGROUNDS = (
    ("Soft studio", "#eef0ed"),
    ("Warm neutral", "#e7e1d9"),
    ("Cool grey", "#d7dbdf"),
)


def _solid_svg(color: str) -> bytes:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800">'
        f'<rect width="600" height="800" fill="{color}"/></svg>'
    ).encode()


def seed(db: Session, storage: LocalStorage) -> None:
    if db.query(DefaultBody).count() == 0:
        keys = {
            view: storage.save((ASSETS / f"body-{view}.jpg").read_bytes(), ".jpg", prefix="seed-")
            for view in ("front", "side", "back")
        }
        for name in ("Default A", "Default B"):
            db.add(
                DefaultBody(
                    name=name, front_key=keys["front"], side_key=keys["side"], back_key=keys["back"]
                )
            )
    if db.query(Background).filter_by(is_preset=True).count() == 0:
        for name, color in PRESET_BACKGROUNDS:
            key = storage.save(_solid_svg(color), ".svg", prefix="seed-")
            db.add(Background(name=name, key=key, is_preset=True))
    db.commit()
