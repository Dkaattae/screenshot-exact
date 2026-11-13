import time
from urllib.parse import parse_qs, urlparse

from tests.conftest import JPEG, add_item


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
