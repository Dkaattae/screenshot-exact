"""Unit tests for file storage, signed URLs and upload checks."""

import io
import time
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.errors import ApiError
from app.storage import LocalStorage, has_file, read_image

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 16


def upload(data: bytes, content_type: str, filename: str = "photo") -> UploadFile:
    return UploadFile(
        file=io.BytesIO(data), filename=filename, headers=Headers({"content-type": content_type})
    )


def query(url: str) -> tuple[str, int, str]:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return parsed.path.rsplit("/", 1)[1], int(params["expires"][0]), params["signature"][0]


@pytest.fixture
def storage(tmp_path) -> LocalStorage:
    return LocalStorage(tmp_path, "storage-secret", "http://api.test/", ttl_seconds=60)


class TestLocalStorage:
    def test_save_writes_the_file_under_a_new_key(self, storage):
        first = storage.save(b"one", ".jpg", prefix="item-")
        second = storage.save(b"two", ".jpg", prefix="item-")
        assert first != second
        assert first.startswith("item-") and first.endswith(".jpg")
        assert (storage.root / first).read_bytes() == b"one"

    def test_url_is_absolute_and_resolves_back_to_the_file(self, storage):
        key = storage.save(b"data", ".png")
        url = storage.url(key)
        assert url.startswith(f"http://api.test/files/{key}?expires=")
        assert storage.resolve(*query(url)) == storage.root / key

    def test_url_expires_after_the_ttl(self, storage):
        key, expires, _ = query(storage.url(storage.save(b"data", ".png")))
        assert time.time() + 50 < expires <= time.time() + 60

    def test_expired_url_does_not_resolve(self, storage):
        key = storage.save(b"data", ".png")
        past = int(time.time()) - 1
        assert storage.resolve(key, past, storage._sign(key, past)) is None

    def test_changing_the_expiry_breaks_the_signature(self, storage):
        key, expires, signature = query(storage.url(storage.save(b"data", ".png")))
        assert storage.resolve(key, expires + 3600, signature) is None

    def test_url_signed_with_another_secret_does_not_resolve(self, storage, tmp_path):
        other = LocalStorage(tmp_path, "other-secret", "http://api.test", ttl_seconds=60)
        key = storage.save(b"data", ".png")
        assert storage.resolve(*query(other.url(key))) is None

    def test_missing_file_does_not_resolve(self, storage):
        assert storage.resolve(*query(storage.url("missing.png"))) is None

    @pytest.mark.parametrize("key", ["../secret.png", "a/b.png", "noextension", ".hidden"])
    def test_unsafe_keys_never_resolve(self, storage, key):
        expires = int(time.time()) + 60
        assert storage.resolve(key, expires, storage._sign(key, expires)) is None

    def test_delete_removes_files_and_skips_unsafe_keys(self, storage, tmp_path):
        outside = tmp_path.parent / "outside.png"
        outside.write_bytes(b"keep")
        key = storage.save(b"data", ".png")
        storage.delete(key, None, "../outside.png", "missing.png")
        assert not (storage.root / key).exists()
        assert outside.exists()

    def test_url_or_none(self, storage):
        assert storage.url_or_none(None) is None
        assert storage.url_or_none("a.png") is not None


class TestReadImage:
    @pytest.mark.parametrize(
        ("data", "content_type", "extension"),
        [(JPEG, "image/jpeg", ".jpg"), (PNG, "image/png", ".png"), (WEBP, "image/webp", ".webp")],
    )
    def test_accepts_supported_images(self, data, content_type, extension):
        assert read_image(upload(data, content_type), "front", 1024) == (data, extension)

    @pytest.mark.parametrize("content_type", ["image/gif", "image/heic", "text/plain", ""])
    def test_rejects_other_types(self, content_type):
        with pytest.raises(ApiError, match="JPEG, PNG or WebP"):
            read_image(upload(JPEG, content_type), "front", 1024)

    @pytest.mark.parametrize(
        ("data", "content_type"),
        [
            (PNG, "image/jpeg"),
            (JPEG, "image/png"),
            (b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 16, "image/webp"),
        ],
    )
    def test_rejects_bytes_that_do_not_match_the_type(self, data, content_type):
        with pytest.raises(ApiError, match="not a valid image"):
            read_image(upload(data, content_type), "front", 1024)

    def test_rejects_an_empty_file(self):
        with pytest.raises(ApiError, match="empty"):
            read_image(upload(b"", "image/jpeg"), "front", 1024)

    def test_size_limit_is_inclusive(self):
        exact = JPEG + b"\x00" * (64 - len(JPEG))
        assert read_image(upload(exact, "image/jpeg"), "front", 64)[0] == exact
        with pytest.raises(ApiError, match="larger than"):
            read_image(upload(exact + b"\x00", "image/jpeg"), "front", 64)

    def test_error_names_the_field(self):
        with pytest.raises(ApiError, match="The back photo"):
            read_image(upload(b"", "image/jpeg"), "back", 1024)


def test_has_file():
    assert has_file(None) is False
    assert has_file(upload(b"", "application/octet-stream", filename="")) is False
    assert has_file(upload(JPEG, "image/jpeg")) is True
