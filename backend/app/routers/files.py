"""Serves stored images. Not part of the contract: image URLs are opaque to clients."""

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.errors import forbidden
from app.security import Storage

router = APIRouter(tags=["Files"], include_in_schema=False)


@router.get("/files/{key}")
def get_file(key: str, expires: int, signature: str, storage: Storage) -> FileResponse:
    path = storage.resolve(key, expires, signature)
    if path is None:
        raise forbidden("This image link is invalid or has expired.")
    return FileResponse(
        path,
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
        },
    )
