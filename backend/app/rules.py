"""Outfit rules shared by the outfit and generation endpoints.

These match frontend/src/api/rules.ts, so the mock and the backend behave the same.
"""

import copy
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models import Background, BodyProfile, DefaultBody, Item, User
from app.schemas import OutfitState

# Which slot each outfit field must point at.
_SLOT_FIELDS = (
    ("top_id", "top", "top"),
    ("bottom_id", "bottom", "bottom"),
    ("one_piece_id", "one_piece", "one-piece"),
)


def outfit_item_ids(state: dict[str, Any]) -> list[str]:
    """Item ids worn in the outfit, base first."""
    base = state["base"]
    ids = (
        [base.get("one_piece_id")]
        if base["mode"] == "one_piece"
        else [base.get("top_id"), base.get("bottom_id")]
    )
    ids += [(state.get("outer") or {}).get("item_id"), (state.get("accessory") or {}).get("item_id")]
    return [item_id for item_id in ids if item_id]


def validation_errors(db: Session, user: User, state: OutfitState) -> list[str]:
    """Messages for everything that keeps this outfit from being generated."""
    errors: list[str] = []
    base = state.base
    if base.mode == "top_bottom":
        if not base.top_id:
            errors.append("Choose a top.")
        if not base.bottom_id:
            errors.append("Choose a bottom.")
    elif not base.one_piece_id:
        errors.append("Choose a one-piece.")

    if not state.body.id:
        errors.append("Choose a body.")
    elif state.body.kind == "user":
        profile = db.query(BodyProfile).filter_by(user_id=user.id).one_or_none()
        if profile is None or profile.id != state.body.id:
            errors.append("Your body photos were not found. Choose a body again.")
    elif db.get(DefaultBody, state.body.id) is None:
        errors.append("That default body was not found.")

    if not state.background_id:
        errors.append("Choose a background.")
    else:
        background = db.get(Background, state.background_id)
        if background is None or (not background.is_preset and background.user_id != user.id):
            errors.append("That background was not found.")

    expected = {
        getattr(base, field): (slot, label)
        for field, slot, label in _SLOT_FIELDS
        if getattr(base, field, None)
    }
    if state.outer:
        expected[state.outer.item_id] = ("outer", "outer layer")
    if state.accessory:
        expected[state.accessory.item_id] = ("accessory", "accessory")
    for item_id, (slot, label) in expected.items():
        item = db.get(Item, item_id)
        if item is None or item.user_id != user.id:
            errors.append(f"The chosen {label} is not in your wardrobe.")
        elif item.slot != slot:
            errors.append(f"The chosen {label} is not a {label}.")
    return errors


def edit_state(state: dict[str, Any], message: str) -> tuple[dict[str, Any], str]:
    """PLACEHOLDER for the LLM edit parser: keyword matching, same as the frontend mock."""
    result = copy.deepcopy(state)
    text = message.lower()
    summary = "That request wasn't understood. Try “tuck the shirt” or “open the jacket”."
    if result["base"]["mode"] == "top_bottom" and re.search(r"untuck|tuck", text):
        result["base"]["tucked"] = "untuck" not in text
        summary = "Shirt tucked in." if result["base"]["tucked"] else "Shirt untucked."
    elif result.get("outer") and re.search(r"open|clos", text):
        result["outer"]["open"] = "open" in text
        summary = "Outer layer opened." if result["outer"]["open"] else "Outer layer closed."
    return result, summary


def reused_layers(
    previous: dict[str, Any] | None, current: dict[str, Any]
) -> list[dict[str, Any]]:
    """Which layers a new job can take from the previous finished job's cache."""
    common = previous is not None and all(
        previous.get(key) == current.get(key)
        for key in ("base", "body", "background_id", "style_notes")
    )
    outer = common and previous is not None and previous.get("outer") == current.get("outer")
    accessory = outer and previous is not None and previous.get("accessory") == current.get(
        "accessory"
    )
    return [
        {"layer": "base", "reused": common},
        {"layer": "outer", "reused": outer},
        {"layer": "accessory", "reused": accessory},
    ]
