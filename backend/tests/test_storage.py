"""Unit tests for file storage, signed URLs and upload checks."""

import io
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.config import Settings
from app.errors import ApiError
from app.storage import (
    SHARED,
    FallbackStorage,
    LocalStorage,
    S3Storage,
    content_type,
    has_file,
    make_storage,
    read_image,
)
from tests.conftest import unreachable_s3

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
    return parsed.path.split("/files/", 1)[1], int(params["expires"][0]), params["signature"][0]


@pytest.fixture
def storage(tmp_path) -> LocalStorage:
    return LocalStorage(tmp_path, "storage-secret", "http://api.test/", ttl_seconds=60)


class TestLocalStorage:
    def test_write_read_and_list(self, storage):
        storage.write("inputs/u1/b.jpg", b"two")
        storage.write("inputs/u1/a.jpg", b"one")
        assert storage.read("inputs/u1/a.jpg") == b"one"
        assert storage.list("inputs/u1") == ["a.jpg", "b.jpg"]
        assert storage.list("inputs/nobody") == []

    def test_url_is_absolute_and_resolves_back_to_the_file(self, storage):
        storage.write("inputs/u1/a.png", b"data")
        url = storage.url("inputs/u1/a.png")
        assert url.startswith("http://api.test/files/inputs/u1/a.png?expires=")
        assert storage.resolve(*query(url)) == storage.root / "inputs/u1/a.png"

    def test_url_expires_after_the_ttl(self, storage):
        _, expires, _ = query(storage.url("a.png"))
        assert time.time() + 50 < expires <= time.time() + 60

    def test_expired_url_does_not_resolve(self, storage):
        storage.write("a.png", b"data")
        past = int(time.time()) - 1
        assert storage.resolve("a.png", past, storage._sign("a.png", past)) is None

    def test_changing_the_expiry_breaks_the_signature(self, storage):
        storage.write("a.png", b"data")
        key, expires, signature = query(storage.url("a.png"))
        assert storage.resolve(key, expires + 3600, signature) is None

    def test_url_signed_with_another_secret_does_not_resolve(self, storage, tmp_path):
        other = LocalStorage(tmp_path, "other-secret", "http://api.test", ttl_seconds=60)
        storage.write("a.png", b"data")
        assert storage.resolve(*query(other.url("a.png"))) is None

    def test_missing_file_does_not_resolve(self, storage):
        assert storage.resolve(*query(storage.url("missing.png"))) is None

    @pytest.mark.parametrize(
        "key", ["../secret.png", "a/b/c/d.png", "a/../b.png", "noextension", ".hidden"]
    )
    def test_unsafe_keys_never_resolve(self, storage, key):
        expires = int(time.time()) + 60
        assert storage.resolve(key, expires, storage._sign(key, expires)) is None

    @pytest.mark.parametrize("key", ["../secret.png", "missing.png"])
    def test_read_refuses_unsafe_or_missing_keys(self, storage, key):
        with pytest.raises(FileNotFoundError):
            storage.read(key)

    def test_write_refuses_unsafe_keys(self, storage):
        with pytest.raises(FileNotFoundError):
            storage.write("../x.png", b"data")

    def test_delete_removes_files_and_skips_unsafe_keys(self, storage, tmp_path):
        outside = tmp_path.parent / "outside.png"
        outside.write_bytes(b"keep")
        storage.write("a.png", b"data")
        storage.delete("a.png", None, "../outside.png", "missing.png")
        assert not storage.exists("a.png")
        assert outside.exists()


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


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("a.jpg", "image/jpeg"),
        ("a.mp4", "video/mp4"),
        ("a.svg", "image/svg+xml"),
        ("a.bin", "application/octet-stream"),
    ],
)
def test_content_type(key, expected):
    assert content_type(key) == expected


class TestS3Storage:
    """Against LocalStack (see conftest.localstack_s3)."""

    def test_write_read_list_with_content_type(self, localstack_s3):
        localstack_s3.write("outputs/u1/turn.mp4", b"video")
        assert localstack_s3.read("outputs/u1/turn.mp4") == b"video"
        assert localstack_s3.list("outputs/u1") == ["turn.mp4"]
        assert localstack_s3.list("outputs/u2") == []
        head = localstack_s3._client.head_object(
            Bucket=localstack_s3.bucket, Key="outputs/u1/turn.mp4"
        )
        assert head["ContentType"] == "video/mp4"

    def test_list_does_not_mix_in_sibling_folders(self, localstack_s3):
        localstack_s3.write("inputs/u1/a.jpg", b"1")
        localstack_s3.write("inputs/u10/b.jpg", b"2")
        assert localstack_s3.list("inputs/u1") == ["a.jpg"]

    def test_presigned_url_downloads_the_file(self, localstack_s3):
        localstack_s3.write("inputs/u1/a.png", b"data")
        url = localstack_s3.url("inputs/u1/a.png")
        assert parse_qs(urlparse(url).query)["X-Amz-Expires"] == ["60"]
        response = httpx.get(url)
        assert response.status_code == 200 and response.content == b"data"

    def test_delete_removes_objects_and_skips_unsafe_keys(self, localstack_s3):
        localstack_s3.write("a.png", b"data")
        localstack_s3.delete("a.png", None, "../other.png", "missing.png")
        with pytest.raises(FileNotFoundError):
            localstack_s3.read("a.png")

    @pytest.mark.parametrize("key", ["missing.png", "../x.png"])
    def test_read_missing_or_unsafe_key(self, localstack_s3, key):
        with pytest.raises(FileNotFoundError):
            localstack_s3.read(key)

    def test_custom_endpoint_uses_path_style(self):
        store = S3Storage.connect(
            "tryon-test",
            60,
            endpoint_url="https://storage.example",
            region="eu-north1",
            access_key_id="id",
            secret_access_key="secret",
        )
        assert store.url("a.png").startswith("https://storage.example/tryon-test/a.png?")


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, operation, path, error):
        self.calls.append((operation, path, type(error).__name__))


class CountingS3(S3Storage):
    """LocalStack S3 that counts calls, to show a folder is listed once."""

    def __init__(self, inner: S3Storage):
        super().__init__(inner.bucket, 60, inner._client)
        self.lists = 0
        self.reads = 0

    def list(self, folder):
        self.lists += 1
        return super().list(folder)

    def read(self, key):
        self.reads += 1
        return super().read(key)


@pytest.fixture
def local(tmp_path) -> LocalStorage:
    return LocalStorage(tmp_path / "files", "storage-secret", "http://api.test", ttl_seconds=60)


class TestPaths:
    def test_paths_are_area_then_owner(self, local):
        store = FallbackStorage(local)
        assert store.input_path("u1", "a.jpg") == "inputs/u1/a.jpg"
        assert store.output_path("u1", "a.mp4") == "outputs/u1/a.mp4"
        assert store.input_folder(SHARED).path == "inputs/shared"

    def test_area_folders_are_arguments(self, local):
        store = FallbackStorage(local, input_prefix="uploads/", output_prefix="renders")
        assert store.input_path("u1", "a.jpg") == "uploads/u1/a.jpg"
        assert store.output_folder("u1").path == "renders/u1"

    @pytest.mark.parametrize("prefix", ["a/b", "..", "", "with space"])
    def test_rejects_area_folders_that_are_not_one_plain_name(self, local, prefix):
        with pytest.raises(ValueError, match="one plain name"):
            FallbackStorage(local, input_prefix=prefix)

    @pytest.mark.parametrize("owner", ["..", "a/b", ""])
    def test_rejects_unsafe_owners(self, local, owner):
        with pytest.raises(ValueError, match="one plain name"):
            FallbackStorage(local).input_folder(owner)

    @pytest.mark.parametrize("name", ["../x.jpg", "a/b.jpg", "noext"])
    def test_rejects_unsafe_file_names(self, local, name):
        store = FallbackStorage(local)
        with pytest.raises(ValueError, match="Unsafe"):
            store.input_path("u1", name)
        with pytest.raises(ValueError, match="Unsafe"):
            store.input_folder("u1").write(name, b"x")

    def test_save_makes_a_new_name_in_the_folder(self, local):
        folder = FallbackStorage(local).input_folder("u1")
        first = folder.save(b"a", ".jpg", prefix="item-")
        second = folder.save(b"b", ".jpg", prefix="item-")
        assert first != second and first.startswith("inputs/u1/item-")
        with pytest.raises(ValueError, match="Unsafe"):
            folder.save(b"c", ".jpg", prefix="../")


class TestLocalOnly:
    def test_folder_lives_on_local_disk(self, local):
        recorder = Recorder()
        store = FallbackStorage(local, on_fallback=recorder)
        folder = store.output_folder("u1")
        assert folder.location == "local"
        key = folder.write("front.jpg", b"img")
        assert (local.root / key).read_bytes() == b"img"
        again = store.output_folder("u1")
        assert again.names() == ["front.jpg"] and again.read("front.jpg") == b"img"
        assert again.url("front.jpg").startswith("http://api.test/files/outputs/u1/front.jpg?")
        assert recorder.calls == []


class TestS3Reachable:
    def test_folder_is_listed_once_then_every_file_loads_from_s3(self, local, localstack_s3):
        for view in ("front", "side", "back"):
            localstack_s3.write(f"inputs/u1/{view}.jpg", view.encode())
        s3 = CountingS3(localstack_s3)
        folder = FallbackStorage(local, s3).input_folder("u1")
        assert folder.location == "s3"
        assert folder.read_all() == {
            "back.jpg": b"back",
            "front.jpg": b"front",
            "side.jpg": b"side",
        }
        assert s3.lists == 1 and s3.reads == 3

    def test_writes_go_to_s3_not_local(self, local, localstack_s3):
        folder = FallbackStorage(local, localstack_s3).output_folder("u1")
        key = folder.write("front.jpg", b"img")
        assert localstack_s3.read(key) == b"img" and not local.exists(key)
        assert httpx.get(folder.url("front.jpg")).content == b"img"

    def test_local_files_from_an_outage_are_merged_in(self, local, localstack_s3):
        localstack_s3.write("inputs/u1/a.jpg", b"from s3")
        local.write("inputs/u1/b.jpg", b"from the outage")
        store = FallbackStorage(local, localstack_s3)
        folder = store.input_folder("u1")
        assert folder.files == {"a.jpg": "s3", "b.jpg": "local"}
        assert folder.read_all() == {"a.jpg": b"from s3", "b.jpg": b"from the outage"}
        assert folder.url("b.jpg").startswith("http://api.test/files/")
        assert store.read("inputs/u1/b.jpg") == b"from the outage"

    def test_s3_errors_that_are_not_connection_errors_do_not_fall_back(self, local, localstack_s3):
        wrong_bucket = S3Storage(f"{localstack_s3.bucket}-missing", 60, localstack_s3._client)
        recorder = Recorder()
        with pytest.raises(Exception, match="NoSuchBucket"):
            FallbackStorage(local, wrong_bucket, on_fallback=recorder).input_folder("u1")
        assert recorder.calls == []

    def test_delete_removes_both_copies(self, local, localstack_s3):
        store = FallbackStorage(local, localstack_s3)
        localstack_s3.write("inputs/u1/x.jpg", b"s3")
        local.write("inputs/u1/x.jpg", b"local")
        store.delete("inputs/u1/x.jpg")
        assert not local.exists("inputs/u1/x.jpg")
        with pytest.raises(FileNotFoundError):
            localstack_s3.read("inputs/u1/x.jpg")


class TestS3Unreachable:
    def test_listing_fails_once_and_the_whole_folder_uses_local_disk(self, local):
        local.write("inputs/u1/front.jpg", b"f")
        local.write("inputs/u1/back.jpg", b"b")
        recorder = Recorder()
        folder = FallbackStorage(local, unreachable_s3(), on_fallback=recorder).input_folder("u1")
        assert folder.location == "local"
        assert folder.read_all() == {"back.jpg": b"b", "front.jpg": b"f"}
        folder.write("side.jpg", b"s")
        assert local.read("inputs/u1/side.jpg") == b"s"
        # One fallback for the folder, not one per file.
        assert recorder.calls == [("list", "inputs/u1", "EndpointConnectionError")]

    def test_s3_lost_mid_folder_switches_the_rest_to_local(self, local, localstack_s3):
        recorder = Recorder()
        store = FallbackStorage(local, localstack_s3, on_fallback=recorder)
        folder = store.output_folder("u1")
        assert folder.location == "s3"
        store.s3 = unreachable_s3()
        folder.write("front.jpg", b"f")
        folder.write("side.jpg", b"s")
        assert folder.location == "local"
        assert local.read("outputs/u1/front.jpg") == b"f"
        assert local.read("outputs/u1/side.jpg") == b"s"
        assert [call[0] for call in recorder.calls] == ["write"]

    def test_single_key_read_and_delete_fall_back(self, local):
        recorder = Recorder()
        store = FallbackStorage(local, unreachable_s3(), on_fallback=recorder)
        local.write("inputs/u1/a.jpg", b"a")
        assert store.read("inputs/u1/a.jpg") == b"a"
        assert store.url("inputs/u1/a.jpg").startswith("http://api.test/files/")
        store.delete("inputs/u1/a.jpg")
        assert not local.exists("inputs/u1/a.jpg")
        assert [call[0] for call in recorder.calls] == ["read", "delete"]

    def test_default_callback_logs_a_warning(self, local, caplog):
        FallbackStorage(local, unreachable_s3()).input_folder("u1")
        assert "S3 list of inputs/u1 failed, using local disk" in caplog.text


class TestMakeStorage:
    def test_local_only_without_a_bucket(self, tmp_path):
        store = make_storage(Settings(storage_dir=str(tmp_path)))
        assert store.s3 is None
        assert store.input_path("u1", "a.jpg") == "inputs/u1/a.jpg"

    def test_s3_first_with_a_bucket_and_folders_from_settings(self, tmp_path):
        settings = Settings(
            storage_dir=str(tmp_path),
            s3_bucket="b",
            s3_region="us-east-1",
            input_prefix="in",
            output_prefix="out",
        )
        store = make_storage(settings)
        assert isinstance(store.s3, S3Storage) and store.s3.bucket == "b"
        assert store.output_path("u1", "a.jpg") == "out/u1/a.jpg"
