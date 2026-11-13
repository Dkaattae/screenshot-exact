from fastapi import APIRouter

from app.errors import not_found
from app.models import Job
from app.schemas import JobOut
from app.security import CurrentUser, DbSession, Storage
from app.serialize import job_out

router = APIRouter(tags=["Generation"])


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, user: CurrentUser, db: DbSession, storage: Storage) -> JobOut:
    job = db.get(Job, job_id)
    # Another user's job reads as missing, so job ids can't be probed.
    if job is None or job.user_id != user.id:
        raise not_found("Generation")
    return job_out(job, storage)
