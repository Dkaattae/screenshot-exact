"""Request and response shapes. These mirror the schemas in ../openapi.yaml."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Slot = Literal["top", "one_piece", "bottom", "outer", "accessory"]
View = Literal["front", "side", "back"]
Layer = Literal["base", "outer", "accessory"]
JobStatus = Literal["queued", "running", "done", "failed"]
VIEWS: tuple[View, ...] = ("front", "side", "back")

Measurements = dict[str, float | None]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _reject_nulls(data: Any, fields: tuple[str, ...]) -> Any:
    """For PATCH bodies: these fields may be left out but not set to null."""
    if isinstance(data, dict):
        for field in fields:
            if field in data and data[field] is None:
                raise ValueError(f"{field} cannot be null")
    return data


# Auth


class RegisterIn(Strict):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(Strict):
    email: EmailStr
    password: str = Field(max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserOut


# Profile, bodies and backgrounds


class ViewImages(BaseModel):
    front: str
    side: str
    back: str


class BodyProfileOut(BaseModel):
    id: str
    user_id: str
    height_cm: float | None
    images: ViewImages
    measurements: Measurements
    consent_at: datetime
    updated_at: datetime


class ProfileOut(BaseModel):
    body: BodyProfileOut | None


class DefaultBodyOut(BaseModel):
    id: str
    name: str
    images: ViewImages


class BackgroundOut(BaseModel):
    id: str
    name: str
    url: str
    is_preset: bool


# Wardrobe


class ItemOut(BaseModel):
    id: str
    user_id: str
    slot: Slot
    name: str
    front_url: str
    back_url: str | None
    measurements: Measurements
    created_at: datetime


class ItemPatch(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slot: Slot | None = None
    measurements: Measurements | None = None

    @model_validator(mode="before")
    @classmethod
    def no_nulls(cls, data: Any) -> Any:
        return _reject_nulls(data, ("name", "slot", "measurements"))


# Outfits


class BodyRef(Strict):
    kind: Literal["user", "default"]
    id: str


class TopBottomBase(Strict):
    mode: Literal["top_bottom"]
    top_id: str
    bottom_id: str | None
    tucked: bool


class OnePieceBase(Strict):
    mode: Literal["one_piece"]
    one_piece_id: str


OutfitBase = Annotated[TopBottomBase | OnePieceBase, Field(discriminator="mode")]


class OuterSelection(Strict):
    item_id: str
    open: bool = False


class AccessorySelection(Strict):
    item_id: str


class OutfitState(Strict):
    body: BodyRef
    background_id: str
    base: OutfitBase
    outer: OuterSelection | None
    accessory: AccessorySelection | None
    style_notes: dict[str, str]


class OutfitCreate(Strict):
    state: OutfitState
    name: str | None = Field(default=None, max_length=200)


class OutfitPatch(Strict):
    name: str | None = Field(default=None, max_length=200)
    favorite: bool | None = None
    body: BodyRef | None = None
    background_id: str | None = None
    base: OutfitBase | None = None
    outer: OuterSelection | None = None
    accessory: AccessorySelection | None = None
    style_notes: dict[str, str] | None = None

    @model_validator(mode="before")
    @classmethod
    def no_nulls(cls, data: Any) -> Any:
        return _reject_nulls(
            data, ("favorite", "body", "background_id", "base", "style_notes")
        )

    @model_validator(mode="after")
    def not_empty(self) -> "OutfitPatch":
        if not self.model_fields_set:
            raise ValueError("Send at least one field to change.")
        return self


class OutfitOut(BaseModel):
    id: str
    user_id: str
    name: str | None
    favorite: bool
    state: OutfitState
    version: int
    created_at: datetime
    updated_at: datetime


class EditIn(Strict):
    message: str = Field(min_length=1, max_length=1000)

    @field_validator("message")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Type what you'd like to change.")
        return value


class EditOut(BaseModel):
    outfit: OutfitOut
    change_summary: str


# Generation


class GenerateOut(BaseModel):
    job_id: str


class ViewResult(BaseModel):
    status: JobStatus
    url: str | None
    inferred_item_ids: list[str]


class JobViews(BaseModel):
    front: ViewResult
    side: ViewResult
    back: ViewResult


class LayerReuse(BaseModel):
    layer: Layer
    reused: bool


class Timings(BaseModel):
    total: int | None


class JobOut(BaseModel):
    id: str
    outfit_id: str
    outfit_version: int
    status: JobStatus
    views: JobViews
    layers: list[LayerReuse]
    timings_ms: Timings
    cost_usd: float | None
    error: str | None
    created_at: datetime
