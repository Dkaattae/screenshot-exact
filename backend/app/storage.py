"""File storage on local disk, served through signed, expiring URLs.

The database stores storage keys, never URLs. URLs are signed when a response is
built, so they can expire and later point at object storage without a schema change.
"""

import hashlib
import hmac
import re
import time
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.errors import validation_error

KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]+\.[a-z0-9]+$")

IMAGE_TYPES = {
    "image/jpeg": (".jpg", (b"\xff\xd8\xff",)),
    "image/png": (".png", (b"\x89PNG\r\n\x1a\n",)),
    "image/webp": (".webp", (b"RIFF",)),
}


class LocalStorage:
    def __init__(self, root: str | Path, secret: str, base_url: str, ttl_seconds: int) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._secret = secret.encode()
        self._base_url = base_url.rstrip("/")
        self._ttl = ttl_seconds

    def save(self, data: bytes, extension: str, prefix: str = "") -> str:
        key = f"{prefix}{uuid.uuid4().hex}{extension}"
        (self.root / key).write_bytes(data)
        return key

    def delete(self, *keys: str | None) -> None:
        for key in keys:
            if key and KEY_PATTERN.match(key):
                (self.root / key).unlink(missing_ok=True)

    def url(self, key: str) -> str:
        expires = int(time.time()) + self._ttl
        return f"{self._base_url}/files/{key}?expires={expires}&signature={self._sign(key, expires)}"

    def url_or_none(self, key: str | None) -> str | None:
        return self.url(key) if key else None

    def resolve(self, key: str, expires: int, signature: str) -> Path | None:
        """The file's path when the signature is valid and not expired, otherwise None."""
        if not KEY_PATTERN.match(key) or expires < time.time():
            return None
        if not hmac.compare_digest(signature, self._sign(key, expires)):
            return None
        path = self.root / key
        return path if path.is_file() else None

    def _sign(self, key: str, expires: int) -> str:
        return hmac.new(self._secret, f"{key}:{expires}".encode(), hashlib.sha256).hexdigest()


def read_image(upload: UploadFile, field: str, max_bytes: int) -> tuple[bytes, str]:
    """Check an uploaded image's type, size and leading bytes. Returns (data, extension)."""
    kind = IMAGE_TYPES.get(upload.content_type or "")
    if kind is None:
        raise validation_error(f"The {field} photo must be a JPEG, PNG or WebP image.")
    extension, signatures = kind
    data = upload.file.read(max_bytes + 1)
    if not data:
        raise validation_error(f"The {field} photo is empty.")
    if len(data) > max_bytes:
        raise validation_error(f"The {field} photo is larger than {max_bytes // (1024 * 1024)} MB.")
    if not data.startswith(signatures) or (extension == ".webp" and data[8:12] != b"WEBP"):
        raise validation_error(f"The {field} photo is not a valid image.")
    return data, extension


def has_file(upload: UploadFile | None) -> bool:
    """Browsers can send an empty part for a file input left blank."""
    return upload is not None and bool(upload.filename)
