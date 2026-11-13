"""End-to-end behavior that the per-endpoint tests don't cover."""

from pathlib import Path
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from app import jobs
from app.generation import GenerationNotImplemented
from app.main import create_app
from app.models import User
from tests.conftest import add_item, jpeg, register


def stored_file(settings, url: str) -> Path:
    return Path(settings.storage_dir) / urlparse(url).path.rsplit("/", 1)[1]


def generate(client, auth, outfit_id):
    response = client.post(f"/users/me/outfits/{outfit_id}/generate", headers=auth)
    assert response.status_code == 202, response.text
    return client.get(f"/jobs/{response.json()['job_id']}", headers=auth).json()


def save_body(client, auth):
    files = {"front": jpeg(), "side": jpeg(), "back": jpeg()}
    response = client.put("/users/me/body", headers=auth, files=files, data={"consent": "true"})
    assert response.status_code == 200, response.text
    return response.json()


class TestErrors:
    def test_unknown_route_uses_the_error_shape(self, client):
        response = client.get("/nope")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_wrong_method_uses_the_error_shape(self, client):
        response = client.delete("/bodies/defaults")
        assert response.status_code == 405
        assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"

    def test_malformed_json_is_a_validation_error(self, client, auth, outfit):
        response = client.patch(
            f"/users/me/outfits/{outfit['id']}",
            headers={**auth, "Content-Type": "application/json"},
            content=b"{not json",
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


class TestCors:
    def test_preflight_from_the_frontend_is_allowed(self, client):
        response = client.options(
            "/users/me/items",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

    def test_other_origins_get_no_cors_headers(self, client):
        response = client.get("/bodies/defaults", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in response.headers


class TestAuthEdges:
    def test_token_for_a_deleted_user_is_rejected(self, client, auth):
        with client.app.state.sessionmaker() as db:
            db.query(User).delete()
            db.commit()
        assert client.get("/auth/me", headers=auth).status_code == 401

    def test_non_bearer_scheme_is_rejected(self, client):
        response = client.get("/auth/me", headers={"Authorization": "Basic dXNlcjpwYXNz"})
        assert response.status_code == 401

    def test_login_email_is_case_insensitive(self, client):
        register(client, "Mixed@Example.com")
        response = client.post(
            "/auth/login", json={"email": "MIXED@example.com", "password": "correct-horse"}
        )
        assert response.status_code == 200


class TestSeed:
    def test_restarting_does_not_duplicate_seed_data(self, settings):
        create_app(settings)
        with TestClient(create_app(settings)) as client:
            assert len(client.get("/bodies/defaults").json()) == 2
            backgrounds = client.get("/users/me/backgrounds", headers=register(client)).json()
            assert len(backgrounds) == 3

    def test_seed_images_are_served(self, client):
        body = client.get("/bodies/defaults").json()[0]
        for url in body["images"].values():
            parsed = urlparse(url)
            response = client.get(f"{parsed.path}?{parsed.query}")
            assert response.status_code == 200
            assert response.content.startswith(b"\xff\xd8\xff")


class TestFilesOnDisk:
    def test_deleting_an_item_deletes_its_photos(self, client, auth, settings):
        item = add_item(client, auth, "top", "Shirt")
        paths = [stored_file(settings, item["front_url"]), stored_file(settings, item["back_url"])]
        assert all(path.exists() for path in paths)
        client.delete(f"/users/me/items/{item['id']}", headers=auth)
        assert not any(path.exists() for path in paths)

    def test_replacing_body_photos_deletes_the_old_ones(self, client, auth, settings):
        old = stored_file(settings, save_body(client, auth)["images"]["front"])
        new = stored_file(settings, save_body(client, auth)["images"]["front"])
        assert not old.exists()
        assert new.exists()

    def test_deleting_body_data_deletes_the_photos(self, client, auth, settings):
        images = save_body(client, auth)["images"]
        client.delete("/users/me/body", headers=auth)
        assert not any(stored_file(settings, url).exists() for url in images.values())


class TestOutfitEdges:
    def test_outfit_on_your_own_body(self, client, auth, outfit_state):
        profile = save_body(client, auth)
        outfit_state["body"] = {"kind": "user", "id": profile["id"]}
        outfit = client.post("/users/me/outfits", headers=auth, json={"state": outfit_state})
        assert outfit.status_code == 201, outfit.text

        client.delete("/users/me/body", headers=auth)
        response = client.post(f"/users/me/outfits/{outfit.json()['id']}/generate", headers=auth)
        assert response.status_code == 400
        assert "body photos were not found" in response.json()["error"]["message"]

    def test_another_users_background_is_rejected(self, client, auth, outfit_state):
        other = register(client, "other@example.com")
        background = client.post(
            "/users/me/backgrounds", headers=other, files={"file": jpeg()}, data={"name": "Theirs"}
        ).json()
        outfit_state["background_id"] = background["id"]
        response = client.post("/users/me/outfits", headers=auth, json={"state": outfit_state})
        assert response.status_code == 400
        assert "background was not found" in response.json()["error"]["message"]

    def test_your_own_uploaded_background_is_accepted(self, client, auth, outfit_state):
        background = client.post(
            "/users/me/backgrounds", headers=auth, files={"file": jpeg()}, data={"name": "Mine"}
        ).json()
        outfit_state["background_id"] = background["id"]
        response = client.post("/users/me/outfits", headers=auth, json={"state": outfit_state})
        assert response.status_code == 201, response.text

    def test_rejected_patch_leaves_the_outfit_unchanged(self, client, auth, outfit):
        url = f"/users/me/outfits/{outfit['id']}"
        base = {**outfit["state"]["base"], "top_id": "missing"}
        assert client.patch(url, headers=auth, json={"base": base}).status_code == 400
        current = client.get(url, headers=auth).json()
        assert current["version"] == 1
        assert current["state"] == outfit["state"]

    def test_names_are_trimmed_and_blank_means_none(self, client, auth, outfit_state):
        created = client.post(
            "/users/me/outfits", headers=auth, json={"state": outfit_state, "name": "  Sunday  "}
        ).json()
        assert created["name"] == "Sunday"
        url = f"/users/me/outfits/{created['id']}"
        assert client.patch(url, headers=auth, json={"name": "   "}).json()["name"] is None

    def test_unknown_state_fields_are_rejected(self, client, auth, outfit_state):
        outfit_state["views"] = ["front"]
        response = client.post("/users/me/outfits", headers=auth, json={"state": outfit_state})
        assert response.status_code == 400


class TestJobFailures:
    @pytest.fixture(autouse=True)
    def infer(self, monkeypatch):
        monkeypatch.setattr(jobs, "infer_item_view", lambda item, view: f"inferred-{view}.jpg")

    def test_failure_keeps_the_views_that_finished(self, client, auth, outfit, monkeypatch):
        def render(request):
            if request.view == "front":
                return "render-front.jpg"
            raise GenerationNotImplemented("Image generation is not implemented yet.")

        monkeypatch.setattr(jobs, "render_try_on", render)
        job = generate(client, auth, outfit["id"])
        assert job["status"] == "failed"
        assert job["views"]["front"]["status"] == "done"
        assert job["views"]["front"]["url"] is not None
        assert job["views"]["side"] == {**job["views"]["side"], "status": "failed", "url": None}
        assert job["views"]["back"]["status"] == "failed"

    def test_unexpected_errors_get_a_generic_message(self, client, auth, outfit, monkeypatch):
        def render(request):
            raise RuntimeError("model server returned 500: secret details")

        monkeypatch.setattr(jobs, "render_try_on", render)
        job = generate(client, auth, outfit["id"])
        assert job["status"] == "failed"
        assert job["error"] == "The try-on could not be generated. Please try again."

    def test_render_gets_the_body_background_and_inferred_pieces(
        self, client, auth, outfit, wardrobe, monkeypatch
    ):
        requests = []

        def render(request):
            requests.append(request)
            return f"render-{request.view}.jpg"

        monkeypatch.setattr(jobs, "render_try_on", render)
        assert generate(client, auth, outfit["id"])["status"] == "done"
        assert [r.view for r in requests] == ["front", "side", "back"]
        back = requests[2]
        assert back.body_key and back.background_key
        pieces = {piece.item_id: piece for piece in back.pieces}
        assert pieces[wardrobe["bottom"]["id"]].inferred is True
        assert pieces[wardrobe["bottom"]["id"]].photo_key == "inferred-back.jpg"
        assert pieces[wardrobe["top"]["id"]].inferred is False

    def test_a_job_renders_the_state_it_was_created_with(
        self, client, auth, outfit, monkeypatch
    ):
        states = []
        monkeypatch.setattr(
            jobs, "render_try_on", lambda request: states.append(request.state) or "r.jpg"
        )
        generate(client, auth, outfit["id"])
        client.post(
            f"/users/me/outfits/{outfit['id']}/edit", headers=auth, json={"message": "tuck"}
        )
        history = client.get(f"/users/me/outfits/{outfit['id']}/jobs", headers=auth).json()
        assert history[0]["outfit_version"] == 1
        assert states[0]["base"]["tucked"] is False
