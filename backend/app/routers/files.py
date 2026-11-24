"""Serves locally stored files. Not part of the contract: file URLs are opaque to clients.

Files in S3 are served by presigned bucket URLs instead. This route only serves files on
local disk, including ones written there because S3 was unreachable.
"""

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.errors import forbidden
from app.security import Storage
from app.storage import content_type

router = APIRouter(tags=["Files"], include_in_schema=False)


@router.get("/files/{key:path}")
def get_file(key: str, expires: int, signature: str, storage: Storage) -> FileResponse:
    path = storage.resolve(key, expires, signature)
    if path is None:
        raise forbidden("This image link is invalid or has expired.")
    return FileResponse(
        path,
        media_type=content_type(key),
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
        },
    )
