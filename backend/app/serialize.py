"""Turn database rows into response models. Storage keys become signed URLs here."""

from datetime import UTC, datetime

from app.models import Background, BodyProfile, DefaultBody, Item, Job, Outfit, User
from app.schemas import (
    BackgroundOut,
    BodyProfileOut,
    DefaultBodyOut,
    ItemOut,
    JobOut,
    OutfitOut,
    UserOut,
    ViewImages,
)
from app.storage import FallbackStorage


def utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; every stored time is UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, created_at=utc(user.created_at))


def _images(source: BodyProfile | DefaultBody, storage: FallbackStorage) -> ViewImages:
    return ViewImages(
        front=storage.url(source.front_key),
        side=storage.url(source.side_key),
        back=storage.url(source.back_key),
    )


def body_out(profile: BodyProfile, storage: FallbackStorage) -> BodyProfileOut:
    return BodyProfileOut(
        id=profile.id,
        user_id=profile.user_id,
        height_cm=profile.height_cm,
        images=_images(profile, storage),
        measurements=profile.measurements,
        consent_at=utc(profile.consent_at),
        updated_at=utc(profile.updated_at),
    )


def default_body_out(body: DefaultBody, storage: FallbackStorage) -> DefaultBodyOut:
    return DefaultBodyOut(id=body.id, name=body.name, images=_images(body, storage))


def background_out(background: Background, storage: FallbackStorage) -> BackgroundOut:
    return BackgroundOut(
        id=background.id,
        name=background.name,
        url=storage.url(background.key),
        is_preset=background.is_preset,
    )


def item_out(item: Item, storage: FallbackStorage) -> ItemOut:
    return ItemOut(
        id=item.id,
        user_id=item.user_id,
        slot=item.slot,  # type: ignore[arg-type]
        name=item.name,
        front_url=storage.url(item.front_key),
        back_url=storage.url_or_none(item.back_key),
        measurements=item.measurements,
        created_at=utc(item.created_at),
    )


def outfit_out(outfit: Outfit) -> OutfitOut:
    return OutfitOut.model_validate(
        {
            "id": outfit.id,
            "user_id": outfit.user_id,
            "name": outfit.name,
            "favorite": outfit.favorite,
            "state": outfit.state,
            "version": outfit.version,
            "created_at": utc(outfit.created_at),
            "updated_at": utc(outfit.updated_at),
        }
    )


def job_out(job: Job, storage: FallbackStorage) -> JobOut:
    views = {
        view: {
            "status": result["status"],
            "url": storage.url_or_none(result.get("key")),
            "inferred_item_ids": result["inferred_item_ids"],
        }
        for view, result in job.views.items()
    }
    return JobOut.model_validate(
        {
            "id": job.id,
            "outfit_id": job.outfit_id,
            "outfit_version": job.outfit_version,
            "status": job.status,
            "views": views,
            "layers": job.layers,
            "timings_ms": {"total": job.total_ms},
            "cost_usd": job.cost_usd,
            "error": job.error,
            "created_at": utc(job.created_at),
        }
    )
