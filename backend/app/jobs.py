"""Generation jobs: created by POST .../generate, run in the background after the response."""

import logging
import time

from sqlalchemy.orm import Session, sessionmaker

from app.generation import (
    GenerationNotImplemented,
    Piece,
    TryOnRequest,
    infer_item_view,
    render_try_on,
    uploaded_photo_key,
)
from app.models import Background, BodyProfile, DefaultBody, Item, Job, Outfit
from app.rules import outfit_item_ids, reused_layers
from app.schemas import VIEWS

logger = logging.getLogger(__name__)


def _outfit_items(db: Session, user_id: str, state: dict) -> list[Item]:
    items = [db.get(Item, item_id) for item_id in outfit_item_ids(state)]
    # Items deleted since the outfit was saved are left out.
    return [item for item in items if item is not None and item.user_id == user_id]


def create_job(db: Session, outfit: Outfit) -> Job:
    previous = (
        db.query(Job)
        .filter_by(outfit_id=outfit.id, status="done")
        .order_by(Job.created_at.desc())
        .first()
    )
    items = _outfit_items(db, outfit.user_id, outfit.state)
    views = {
        view: {
            "status": "queued",
            "key": None,
            "inferred_item_ids": [i.id for i in items if uploaded_photo_key(i, view) is None],
        }
        for view in VIEWS
    }
    job = Job(
        user_id=outfit.user_id,
        outfit_id=outfit.id,
        outfit_version=outfit.version,
        status="queued",
        views=views,
        layers=reused_layers(previous.state if previous else None, outfit.state),
        state=outfit.state,
    )
    db.add(job)
    db.commit()
    return job


def _body_key(db: Session, user_id: str, state: dict, view: str) -> str:
    body = state["body"]
    if body["kind"] == "user":
        source = db.query(BodyProfile).filter_by(user_id=user_id).one_or_none()
    else:
        source = db.get(DefaultBody, body["id"])
    if source is None:
        raise ValueError("The outfit's body no longer exists.")
    return getattr(source, f"{view}_key")


def _render(db: Session, job: Job) -> None:
    background = db.get(Background, job.state["background_id"])
    if background is None:
        raise ValueError("The outfit's background no longer exists.")
    items = _outfit_items(db, job.user_id, job.state)
    for view in VIEWS:
        pieces = []
        for item in items:
            key = uploaded_photo_key(item, view)
            pieces.append(
                Piece(item.id, item.slot, key or infer_item_view(item, view), key is None)
            )
        image_key = render_try_on(
            TryOnRequest(
                view=view,
                state=job.state,
                body_key=_body_key(db, job.user_id, job.state, view),
                background_key=background.key,
                pieces=pieces,
            )
        )
        views = dict(job.views)
        views[view] = {**views[view], "status": "done", "key": image_key}
        job.views = views
        db.commit()


def run_job(make_session: sessionmaker, job_id: str) -> None:
    with make_session() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = "running"
        job.views = {view: {**result, "status": "running"} for view, result in job.views.items()}
        db.commit()
        started = time.monotonic()
        try:
            _render(db, job)
            job.status = "done"
        except GenerationNotImplemented as exc:
            _fail(job, str(exc))
        except Exception:
            logger.exception("Generation job %s failed", job_id)
            db.rollback()
            _fail(job, "The try-on could not be generated. Please try again.")
        job.total_ms = int((time.monotonic() - started) * 1000)
        db.commit()


def _fail(job: Job, message: str) -> None:
    job.status = "failed"
    job.error = message
    job.views = {
        view: result if result["status"] == "done" else {**result, "status": "failed"}
        for view, result in job.views.items()
    }
