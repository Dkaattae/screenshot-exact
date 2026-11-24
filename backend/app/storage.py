"""File storage: S3-compatible object storage first, local disk as the fallback, per folder.

Files live in folders: <area>/<owner>/<name>, where area is inputs (uploads, generated humans
and scenes) or outputs (try-on stills and videos), and owner is a user id (or "shared" for
seed data). input_path() and output_path() build the keys.

Work on a folder starts with FallbackStorage.folder(): one listing of the folder in S3. That
listing is the reachability check. If it succeeds, the folder uses S3; if S3 is not
configured or not reachable, the folder uses local disk. The decision is made once per
folder, and every file in it is then read and written from that place without another check.

Files written to local disk during an outage still show up while S3 is reachable: the
listing merges in local files that S3 does not have, and reads them from local disk.

The database stores keys, never URLs. URLs are signed when a response is built, so they can
expire, and moving files between S3 and local disk needs no schema change.
"""

import hashlib
import hmac
import logging
import re
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from fastapi import UploadFile

from app.errors import validation_error

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

# Up to two folder levels (<area>/<owner>/), then a file name. No "..", no deeper nesting.
KEY_PATTERN = re.compile(r"^(?:[A-Za-z0-9_-]+/){0,2}[A-Za-z0-9_-]+\.[a-z0-9]+$")
_PLAIN_NAME = re.compile(r"^[A-Za-z0-9_-]+$")

Area = Literal["input", "output"]
Location = Literal["s3", "local"]
FallbackCallback = Callable[[str, str, Exception], None]

# The owner folder for seed data every user sees.
SHARED = "shared"

IMAGE_TYPES = {
    "image/jpeg": (".jpg", (b"\xff\xd8\xff",)),
    "image/png": (".png", (b"\x89PNG\r\n\x1a\n",)),
    "image/webp": (".webp", (b"RIFF",)),
}

# Served content type for each extension a key can have. Generated videos are MP4.
CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".mp4": "video/mp4",
}


def content_type(key: str) -> str:
    return CONTENT_TYPES.get(Path(key).suffix, "application/octet-stream")


def _check_key(key: str) -> None:
    if not KEY_PATTERN.match(key):
        raise FileNotFoundError(key)


def _plain(value: str, what: str) -> str:
    if not _PLAIN_NAME.match(value):
        raise ValueError(f"The {what} must be one plain name, got {value!r}")
    return value


class LocalStorage:
    """Files on local disk, served by the /files route through HMAC-signed URLs."""

    def __init__(self, root: str | Path, secret: str, base_url: str, ttl_seconds: int) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._secret = secret.encode()
        self._base_url = base_url.rstrip("/")
        self._ttl = ttl_seconds

    def list(self, folder: str) -> list[str]:
        """File names directly inside `folder`."""
        path = self.root / folder
        if not path.is_dir():
            return []
        return sorted(p.name for p in path.iterdir() if p.is_file())

    def write(self, key: str, data: bytes) -> None:
        _check_key(key)
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, key: str) -> bytes:
        _check_key(key)
        return (self.root / key).read_bytes()

    def exists(self, key: str) -> bool:
        return bool(KEY_PATTERN.match(key)) and (self.root / key).is_file()

    def delete(self, *keys: str | None) -> None:
        for key in keys:
            if key and KEY_PATTERN.match(key):
                (self.root / key).unlink(missing_ok=True)

    def url(self, key: str) -> str:
        expires = int(time.time()) + self._ttl
        return (
            f"{self._base_url}/files/{key}?expires={expires}&signature={self._sign(key, expires)}"
        )

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


class S3Storage:
    """S3-compatible object storage (AWS S3, Nebius Object Storage, LocalStack, ...).

    URLs are presigned GET URLs, so browsers and generation models fetch files from the
    bucket directly while the bucket itself stays private.
    """

    def __init__(self, bucket: str, ttl_seconds: int, client: Any) -> None:
        self.bucket = bucket
        self._ttl = ttl_seconds
        self._client = client

    @classmethod
    def connect(
        cls,
        bucket: str,
        ttl_seconds: int,
        endpoint_url: str | None = None,
        region: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> "S3Storage":
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            # Path-style addressing works on every S3-compatible service; AWS itself prefers
            # virtual-hosted style. Fail fast when S3 is unreachable, so the fallback is quick.
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path" if endpoint_url else "virtual"},
                connect_timeout=2,
                read_timeout=10,
                retries={"max_attempts": 1},
            ),
        )
        return cls(bucket, ttl_seconds, client)

    def list(self, folder: str) -> list[str]:
        """File names directly inside `folder`. Raises when S3 is unreachable."""
        prefix = f"{folder}/"
        names = []
        pages = self._client.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=prefix, Delimiter="/"
        )
        for page in pages:
            names += [entry["Key"][len(prefix) :] for entry in page.get("Contents", [])]
        return sorted(names)

    def write(self, key: str, data: bytes) -> None:
        _check_key(key)
        self._client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type(key)
        )

    def read(self, key: str) -> bytes:
        _check_key(key)
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
        except self._client.exceptions.NoSuchKey as exc:
            raise FileNotFoundError(key) from exc
        return response["Body"].read()

    def delete(self, *keys: str | None) -> None:
        objects = [{"Key": key} for key in keys if key and KEY_PATTERN.match(key)]
        # delete_objects takes at most 1000 keys per call.
        for start in range(0, len(objects), 1000):
            self._client.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": objects[start : start + 1000], "Quiet": True},
            )

    def url(self, key: str) -> str:
        return self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=self._ttl
        )


def _s3_unreachable(exc: Exception) -> bool:
    """True for connection, timeout and credential errors. False for answers from S3."""
    from botocore.exceptions import BotoCoreError

    return isinstance(exc, BotoCoreError)


class StorageFolder:
    """One <area>/<owner>/ folder, listed once. Made by FallbackStorage.folder()."""

    def __init__(self, store: "FallbackStorage", path: str) -> None:
        self._store = store
        self.path = path
        self.location: Location
        # Where each file in the folder lives.
        self.files: dict[str, Location]
        self.location, self.files = store._list(path)

    def key(self, name: str) -> str:
        return f"{self.path}/{_plain_file(name)}"

    def names(self) -> list[str]:
        return sorted(self.files)

    def read(self, name: str) -> bytes:
        key = self.key(name)
        if self.files.get(name) == "s3" and self._store.s3 is not None:
            return self._store.s3.read(key)
        return self._store.local.read(key)

    def read_all(self) -> dict[str, bytes]:
        """Every file in the folder, by name."""
        return {name: self.read(name) for name in self.names()}

    def write(self, name: str, data: bytes) -> str:
        """Write a file to the folder's location. Returns its key."""
        key = self.key(name)
        if self.location == "s3" and self._store.s3 is not None:
            try:
                self._store.s3.write(key, data)
                self.files[name] = "s3"
                return key
            except Exception as exc:
                if not _s3_unreachable(exc):
                    raise
                # S3 went away mid-way: the rest of this folder's work stays local.
                self._store._fell_back("write", key, exc)
                self.location = "local"
        self._store.local.write(key, data)
        self.files[name] = "local"
        return key

    def save(self, data: bytes, extension: str, prefix: str = "") -> str:
        """Write under a new unique name. Returns its key."""
        return self.write(f"{prefix}{uuid.uuid4().hex}{extension}", data)

    def url(self, name: str) -> str:
        key = self.key(name)
        if self.files.get(name) == "s3" and self._store.s3 is not None:
            return self._store.s3.url(key)
        return self._store.local.url(key)


def _plain_file(name: str) -> str:
    if "/" in name or not KEY_PATTERN.match(name):
        raise ValueError(f"Unsafe file name: {name!r}")
    return name


class FallbackStorage:
    """S3 first, local disk when S3 is not configured or not reachable, decided per folder.

    `input_prefix` and `output_prefix` name the two area folders, in the bucket and under
    the local root alike. `on_fallback(operation, path, error)` is called each time S3 is
    unreachable and local disk is used instead; by default it logs a warning.
    """

    def __init__(
        self,
        local: LocalStorage,
        s3: S3Storage | None = None,
        input_prefix: str = "inputs",
        output_prefix: str = "outputs",
        on_fallback: FallbackCallback | None = None,
    ) -> None:
        self.local = local
        self.s3 = s3
        self._areas = {
            "input": _plain(input_prefix.strip("/"), "storage folder"),
            "output": _plain(output_prefix.strip("/"), "storage folder"),
        }
        self._on_fallback = on_fallback or _log_fallback

    # Folders and paths

    def folder_path(self, area: Area, owner: str) -> str:
        return f"{self._areas[area]}/{_plain(owner, 'folder owner')}"

    def folder(self, area: Area, owner: str) -> StorageFolder:
        """List the folder once (the S3 reachability check) and pick where it lives."""
        return StorageFolder(self, self.folder_path(area, owner))

    def input_folder(self, owner: str) -> StorageFolder:
        return self.folder("input", owner)

    def output_folder(self, owner: str) -> StorageFolder:
        return self.folder("output", owner)

    def input_path(self, owner: str, name: str) -> str:
        return f"{self.folder_path('input', owner)}/{_plain_file(name)}"

    def output_path(self, owner: str, name: str) -> str:
        return f"{self.folder_path('output', owner)}/{_plain_file(name)}"

    # Single files by key, for code that holds a stored key (responses, deletes)

    def read(self, key: str) -> bytes:
        _check_key(key)
        if self.s3 is not None:
            try:
                return self.s3.read(key)
            except FileNotFoundError:
                pass  # Not in S3: it may have been written locally during an outage.
            except Exception as exc:
                if not _s3_unreachable(exc):
                    raise
                self._fell_back("read", key, exc)
        return self.local.read(key)

    def delete(self, *keys: str | None) -> None:
        if self.s3 is not None:
            try:
                self.s3.delete(*keys)
            except Exception as exc:
                if not _s3_unreachable(exc):
                    raise
                self._fell_back("delete", ", ".join(k for k in keys if k), exc)
        self.local.delete(*keys)

    def url(self, key: str) -> str:
        # A local copy only exists when S3 was unavailable at write time, so check it first:
        # it is a cheap disk check, and it avoids a network round trip per URL.
        if self.s3 is None or self.local.exists(key):
            return self.local.url(key)
        return self.s3.url(key)

    def url_or_none(self, key: str | None) -> str | None:
        return self.url(key) if key else None

    def resolve(self, key: str, expires: int, signature: str) -> Path | None:
        """Local files only. S3 files are served by their presigned URLs."""
        return self.local.resolve(key, expires, signature)

    # Internals

    def _list(self, path: str) -> tuple[Location, dict[str, Location]]:
        local_names = self.local.list(path)
        if self.s3 is not None:
            try:
                s3_names = self.s3.list(path)
            except Exception as exc:
                if not _s3_unreachable(exc):
                    raise
                self._fell_back("list", path, exc)
            else:
                files: dict[str, Location] = {name: "local" for name in local_names}
                files.update({name: "s3" for name in s3_names})
                return "s3", files
        return "local", {name: "local" for name in local_names}

    def _fell_back(self, operation: str, path: str, error: Exception) -> None:
        self._on_fallback(operation, path, error)


def _log_fallback(operation: str, path: str, error: Exception) -> None:
    logger.warning("S3 %s of %s failed, using local disk: %s", operation, path, error)


def make_storage(
    settings: "Settings", on_fallback: FallbackCallback | None = None
) -> FallbackStorage:
    """S3 when TRYON_S3_BUCKET is set, with local disk as the fallback; local disk otherwise."""
    s3 = (
        S3Storage.connect(
            bucket=settings.s3_bucket,
            ttl_seconds=settings.file_url_ttl_seconds,
            endpoint_url=settings.s3_endpoint_url,
            region=settings.s3_region,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
        )
        if settings.s3_bucket
        else None
    )
    local = LocalStorage(
        settings.storage_dir,
        settings.secret_key,
        settings.public_base_url,
        settings.file_url_ttl_seconds,
    )
    return FallbackStorage(
        local,
        s3,
        input_prefix=settings.input_prefix,
        output_prefix=settings.output_prefix,
        on_fallback=on_fallback,
    )


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
