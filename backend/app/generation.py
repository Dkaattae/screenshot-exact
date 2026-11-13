"""Try-on image generation: NOT IMPLEMENTED YET.

infer_item_view and render_try_on are where the real models plug in. Until then they
raise GenerationNotImplemented, and every job ends as `failed` with that message.
"""

from dataclasses import dataclass
from typing import Any

from app.models import Item
from app.schemas import View


class GenerationNotImplemented(NotImplementedError):
    pass


@dataclass(frozen=True)
class Piece:
    item_id: str
    slot: str
    photo_key: str
    inferred: bool


@dataclass(frozen=True)
class TryOnRequest:
    view: View
    state: dict[str, Any]
    body_key: str
    background_key: str
    pieces: list[Piece]


def uploaded_photo_key(item: Item, view: View) -> str | None:
    """The photo the user uploaded for this view. Items never have a side photo."""
    if view == "front":
        return item.front_key
    if view == "back":
        return item.back_key
    return None


def infer_item_view(item: Item, view: View) -> str:
    """Generate the unseen view of an item. Returns the new image's storage key."""
    raise GenerationNotImplemented("Inferring item views is not implemented yet.")


def render_try_on(request: TryOnRequest) -> str:
    """Render the outfit on the body for one view. Returns the image's storage key."""
    raise GenerationNotImplemented("Image generation is not implemented yet.")
