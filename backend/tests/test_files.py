import time
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import (
    JPEG,
    LOCALSTACK_ENDPOINT,
    UNREACHABLE_ENDPOINT,
    add_item,
    register,
)


def path_of(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.path}?{parsed.query}"


def test_signed_url_serves_the_file(client, auth):
    item = add_item(client, auth, "top", "Shirt")
    response = client.get(path_of(item["front_url"]))
    assert response.status_code == 200
    assert response.content == JPEG
    assert response.headers["x-content-type-options"] == "nosniff"


def test_tampered_signature_is_rejected(client, auth):
    item = add_item(client, auth, "top", "Shirt")
    url = path_of(item["front_url"])
    response = client.get(url[:-4] + "0000")
    assert response.status_code == 403


def test_signature_does_not_transfer_to_another_file(client, auth):
    shirt = add_item(client, auth, "top", "Shirt")
    jeans = add_item(client, auth, "bottom", "Jeans")
    shirt_query = urlparse(shirt["front_url"]).query
    jeans_path = urlparse(jeans["front_url"]).path
    assert client.get(f"{jeans_path}?{shirt_query}").status_code == 403


def test_expired_url_is_rejected(client, auth, settings):
    item = add_item(client, auth, "top", "Shirt")
    parsed = urlparse(item["front_url"])
    signature = parse_qs(parsed.query)["signature"][0]
    past = int(time.time()) - 10
    assert client.get(f"{parsed.path}?expires={past}&signature={signature}").status_code == 403


def test_path_traversal_is_rejected(client):
    response = client.get("/files/..%2Fapp.db?expires=9999999999&signature=x")
    assert response.status_code in (403, 404)


def test_urls_are_absolute(auth, client):
    item = add_item(client, auth, "top", "Shirt")
    assert item["front_url"].startswith("http://testserver/files/")


def test_video_is_served_as_mp4(client):
    storage = client.app.state.storage
    key = storage.output_folder("u1").save(b"\x00\x00\x00\x18ftypmp42", ".mp4", prefix="job-")
    response = client.get(path_of(storage.url(key)))
    assert response.status_code == 200
    assert response.headers["content-type"] == "video/mp4"


def test_app_stores_uploads_in_s3_and_serves_presigned_urls(settings, localstack_s3):
    s3_settings = settings.model_copy(
        update={
            "s3_bucket": localstack_s3.bucket,
            "s3_endpoint_url": LOCALSTACK_ENDPOINT,
            "s3_region": "us-east-1",
            "s3_access_key_id": "test",
            "s3_secret_access_key": "test",
        }
    )
    with TestClient(create_app(s3_settings)) as s3_client:
        item = add_item(s3_client, register(s3_client), "top", "Shirt")
        assert item["front_url"].startswith(f"{LOCALSTACK_ENDPOINT}/{localstack_s3.bucket}/inputs/")
        assert httpx.get(item["front_url"]).content == JPEG


def test_app_falls_back_to_local_disk_when_s3_is_unreachable(settings):
    down = settings.model_copy(
        update={
            "s3_bucket": "tryon",
            "s3_endpoint_url": UNREACHABLE_ENDPOINT,
            "s3_region": "us-east-1",
            "s3_access_key_id": "test",
            "s3_secret_access_key": "test",
        }
    )
    with TestClient(create_app(down)) as down_client:
        item = add_item(down_client, register(down_client), "top", "Shirt")
        assert item["front_url"].startswith("http://testserver/files/inputs/")
        assert down_client.get(path_of(item["front_url"])).content == JPEG
