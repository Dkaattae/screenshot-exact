from fastapi import APIRouter, BackgroundTasks, Request, Response, status
from pydantic import ValidationError

from app.errors import not_found, validation_error
from app.jobs import create_job, run_job
from app.models import Job, Outfit, User, utcnow
from app.rules import edit_state, validation_errors
from app.schemas import (
    EditIn,
    EditOut,
    GenerateOut,
    JobOut,
    OutfitCreate,
    OutfitOut,
    OutfitPatch,
    OutfitState,
)
from app.security import DbSession, PathUser, Storage
from app.serialize import job_out, outfit_out

router = APIRouter(prefix="/users/{user_id}/outfits", tags=["Outfits"])


def _get_outfit(db: DbSession, user: User, outfit_id: str) -> Outfit:
    outfit = db.get(Outfit, outfit_id)
    if outfit is None or outfit.user_id != user.id:
        raise not_found("Outfit")
    return outfit


def _check(db: DbSession, user: User, state: OutfitState) -> None:
    errors = validation_errors(db, user, state)
    if errors:
        raise validation_error(" ".join(errors))


@router.get("", response_model=list[OutfitOut])
def list_outfits(user: PathUser, db: DbSession) -> list[OutfitOut]:
    outfits = db.query(Outfit).filter_by(user_id=user.id).order_by(Outfit.created_at.desc()).all()
    return [outfit_out(outfit) for outfit in outfits]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=OutfitOut)
def create_outfit(body: OutfitCreate, user: PathUser, db: DbSession) -> OutfitOut:
    _check(db, user, body.state)
    outfit = Outfit(
        user_id=user.id,
        name=body.name.strip() if body.name and body.name.strip() else None,
        state=body.state.model_dump(mode="json"),
        version=1,
    )
    db.add(outfit)
    db.commit()
    return outfit_out(outfit)


@router.get("/{outfit_id}", response_model=OutfitOut)
def get_outfit(outfit_id: str, user: PathUser, db: DbSession) -> OutfitOut:
    return outfit_out(_get_outfit(db, user, outfit_id))


@router.patch("/{outfit_id}", response_model=OutfitOut)
def update_outfit(outfit_id: str, body: OutfitPatch, user: PathUser, db: DbSession) -> OutfitOut:
    outfit = _get_outfit(db, user, outfit_id)
    changes = body.model_dump(mode="json", exclude_unset=True)
    if "name" in changes:
        name = changes.pop("name")
        outfit.name = name.strip() if name and name.strip() else None
    if "favorite" in changes:
        outfit.favorite = changes.pop("favorite")
    if changes:
        try:
            state = OutfitState.model_validate({**outfit.state, **changes})
        except ValidationError as exc:
            raise validation_error("The outfit change is not valid.") from exc
        _check(db, user, state)
        new_state = state.model_dump(mode="json")
        if new_state != outfit.state:
            outfit.state = new_state
            outfit.version += 1
    outfit.updated_at = utcnow()
    db.commit()
    return outfit_out(outfit)


@router.post("/{outfit_id}/edit", response_model=EditOut)
def edit_outfit(outfit_id: str, body: EditIn, user: PathUser, db: DbSession) -> EditOut:
    outfit = _get_outfit(db, user, outfit_id)
    new_state, summary = edit_state(outfit.state, body.message)
    if new_state != outfit.state:
        outfit.state = new_state
        outfit.version += 1
        outfit.updated_at = utcnow()
        db.commit()
    return EditOut(outfit=outfit_out(outfit), change_summary=summary)


@router.delete("/{outfit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_outfit(outfit_id: str, user: PathUser, db: DbSession) -> Response:
    outfit = _get_outfit(db, user, outfit_id)
    db.query(Job).filter_by(outfit_id=outfit.id).delete()
    db.delete(outfit)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{outfit_id}/generate", status_code=status.HTTP_202_ACCEPTED, response_model=GenerateOut
)
def generate_outfit(
    outfit_id: str,
    user: PathUser,
    db: DbSession,
    request: Request,
    background: BackgroundTasks,
) -> GenerateOut:
    outfit = _get_outfit(db, user, outfit_id)
    _check(db, user, OutfitState.model_validate(outfit.state))
    job = create_job(db, outfit)
    background.add_task(run_job, request.app.state.sessionmaker, job.id)
    return GenerateOut(job_id=job.id)


@router.get("/{outfit_id}/jobs", response_model=list[JobOut])
def list_outfit_jobs(
    outfit_id: str, user: PathUser, db: DbSession, storage: Storage
) -> list[JobOut]:
    outfit = _get_outfit(db, user, outfit_id)
    jobs = db.query(Job).filter_by(outfit_id=outfit.id).order_by(Job.created_at.desc()).all()
    return [job_out(job, storage) for job in jobs]
