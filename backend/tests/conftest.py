import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Base, make_engine
from app.main import create_app

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def jpeg(name: str = "photo.jpg") -> tuple[str, bytes, str]:
    return (name, JPEG, "image/jpeg")


# Set to a Postgres URL to run the suite against Postgres. Every table is dropped after
# each test, so never point it at a database whose data you want to keep.
TEST_DATABASE_URL = os.environ.get("TRYON_TEST_DATABASE_URL")


@pytest.fixture
def settings(tmp_path) -> Iterator[Settings]:
    yield Settings(
        database_url=TEST_DATABASE_URL or f"sqlite:///{tmp_path}/test.db",
        storage_dir=str(tmp_path / "files"),
        secret_key="test-secret-that-is-at-least-32-bytes-long",
        public_base_url="http://testserver",
    )
    if TEST_DATABASE_URL:
        engine = make_engine(TEST_DATABASE_URL)
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def register(client: TestClient, email: str = "user@example.com") -> dict[str, str]:
    response = client.post("/auth/register", json={"email": email, "password": "correct-horse"})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def auth(client: TestClient) -> dict[str, str]:
    return register(client)


def add_item(client: TestClient, auth: dict, slot: str, name: str, back: bool = True) -> dict:
    files = {"front": jpeg()}
    if back:
        files["back"] = jpeg("back.jpg")
    response = client.post(
        "/users/me/items",
        headers=auth,
        files=files,
        data={"slot": slot, "name": name, "measurements": '{"waist": 80}'},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def wardrobe(client: TestClient, auth: dict) -> dict[str, dict]:
    return {
        "top": add_item(client, auth, "top", "Shirt"),
        "bottom": add_item(client, auth, "bottom", "Jeans", back=False),
        "outer": add_item(client, auth, "outer", "Trench"),
        "one_piece": add_item(client, auth, "one_piece", "Dress"),
        "accessory": add_item(client, auth, "accessory", "Bag"),
    }


@pytest.fixture
def outfit_state(client: TestClient, auth: dict, wardrobe: dict) -> dict:
    body = client.get("/bodies/defaults").json()[0]
    background = client.get("/users/me/backgrounds", headers=auth).json()[0]
    return {
        "body": {"kind": "default", "id": body["id"]},
        "background_id": background["id"],
        "base": {
            "mode": "top_bottom",
            "top_id": wardrobe["top"]["id"],
            "bottom_id": wardrobe["bottom"]["id"],
            "tucked": False,
        },
        "outer": {"item_id": wardrobe["outer"]["id"], "open": False},
        "accessory": None,
        "style_notes": {},
    }


@pytest.fixture
def outfit(client: TestClient, auth: dict, outfit_state: dict) -> dict:
    response = client.post("/users/me/outfits", headers=auth, json={"state": outfit_state})
    assert response.status_code == 201, response.text
    return response.json()
