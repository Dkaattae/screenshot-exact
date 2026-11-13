import pytest

from app import jobs
from tests.conftest import register


def generate(client, auth, outfit_id):
    response = client.post(f"/users/me/outfits/{outfit_id}/generate", headers=auth)
    assert response.status_code == 202, response.text
    return client.get(f"/jobs/{response.json()['job_id']}", headers=auth).json()


def test_job_fails_clearly_until_generation_is_implemented(client, auth, outfit):
    job = generate(client, auth, outfit["id"])
    assert job["status"] == "failed"
    assert job["error"] == "Image generation is not implemented yet."
    assert {v["status"] for v in job["views"].values()} == {"failed"}
    assert job["timings_ms"]["total"] is not None


def test_job_always_has_all_three_views(client, auth, outfit):
    job = generate(client, auth, outfit["id"])
    assert set(job["views"]) == {"front", "side", "back"}


def test_job_lists_items_without_a_photo_for_each_view(client, auth, outfit, wardrobe):
    views = generate(client, auth, outfit["id"])["views"]
    top, bottom, outer = wardrobe["top"]["id"], wardrobe["bottom"]["id"], wardrobe["outer"]["id"]
    assert views["front"]["inferred_item_ids"] == []
    assert views["back"]["inferred_item_ids"] == [bottom]
    assert views["side"]["inferred_item_ids"] == [top, bottom, outer]


@pytest.fixture
def fake_generation(monkeypatch):
    """Stand-in models, so a job can finish."""
    monkeypatch.setattr(jobs, "infer_item_view", lambda item, view: f"inferred-{view}.jpg")
    monkeypatch.setattr(jobs, "render_try_on", lambda request: f"render-{request.view}.jpg")


def test_job_finishes_with_an_image_per_view(client, auth, outfit, fake_generation):
    job = generate(client, auth, outfit["id"])
    assert job["status"] == "done", job
    assert job["error"] is None
    for view, result in job["views"].items():
        assert result["status"] == "done"
        assert f"/files/render-{view}.jpg?" in result["url"]


def test_layer_reuse_follows_what_changed(client, auth, outfit, fake_generation):
    url = f"/users/me/outfits/{outfit['id']}"
    first = generate(client, auth, outfit["id"])
    assert first["layers"] == [
        {"layer": "base", "reused": False},
        {"layer": "outer", "reused": False},
        {"layer": "accessory", "reused": False},
    ]
    client.patch(url, headers=auth, json={"outer": {**outfit["state"]["outer"], "open": True}})
    second = generate(client, auth, outfit["id"])
    assert [layer["reused"] for layer in second["layers"]] == [True, False, False]
    assert second["outfit_version"] == 2


def test_job_history_is_newest_first(client, auth, outfit):
    first = generate(client, auth, outfit["id"])
    second = generate(client, auth, outfit["id"])
    history = client.get(f"/users/me/outfits/{outfit['id']}/jobs", headers=auth).json()
    assert [j["id"] for j in history] == [second["id"], first["id"]]


def test_generate_rechecks_the_outfit(client, auth, outfit, wardrobe):
    client.delete(f"/users/me/items/{wardrobe['top']['id']}", headers=auth)
    response = client.post(f"/users/me/outfits/{outfit['id']}/generate", headers=auth)
    assert response.status_code == 400


def test_other_users_jobs_are_not_found(client, auth, outfit):
    job = generate(client, auth, outfit["id"])
    other = register(client, "other@example.com")
    assert client.get(f"/jobs/{job['id']}", headers=other).status_code == 404


def test_deleting_an_outfit_deletes_its_jobs(client, auth, outfit):
    job = generate(client, auth, outfit["id"])
    client.delete(f"/users/me/outfits/{outfit['id']}", headers=auth)
    assert client.get(f"/jobs/{job['id']}", headers=auth).status_code == 404
