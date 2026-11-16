"""create_site: the API under /api and the built frontend at /."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_site

SHELL = "<!doctype html><title>shell</title>"


@pytest.fixture
def site(settings, tmp_path) -> TestClient:
    frontend = tmp_path / "frontend"
    (frontend / "assets").mkdir(parents=True)
    (frontend / "_shell.html").write_text(SHELL)
    (frontend / "assets" / "app.js").write_text("console.log(1)")
    settings.frontend_dir = str(frontend)
    settings.public_base_url = "http://testserver/api"
    with TestClient(create_site(settings)) as client:
        yield client


def test_api_is_served_under_api(site):
    response = site.get("/api/bodies/defaults")
    assert response.status_code == 200
    assert response.json()


def test_unknown_api_path_is_a_json_404_not_the_shell(site):
    response = site.get("/api/nope")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_image_urls_resolve_through_api(site):
    url = site.get("/api/bodies/defaults").json()[0]["images"]["front"]
    assert url.startswith("http://testserver/api/files/")
    assert site.get(url).status_code == 200


@pytest.mark.parametrize("path", ["/", "/wardrobe", "/outfits/123"])
def test_client_routes_get_the_shell(site, path):
    response = site.get(path)
    assert response.status_code == 200
    assert response.text == SHELL


def test_assets_are_served_and_missing_assets_404(site):
    assert site.get("/assets/app.js").text == "console.log(1)"
    assert site.get("/assets/missing.js").status_code == 404


def test_frontend_dir_without_shell_fails_at_startup(settings, tmp_path):
    settings.frontend_dir = str(tmp_path)
    with pytest.raises(RuntimeError, match="_shell.html"):
        create_site(settings)


def test_without_frontend_dir_only_the_api_is_served(settings):
    with TestClient(create_site(settings)) as client:
        assert client.get("/api/bodies/defaults").status_code == 200
        assert client.get("/").status_code == 404
