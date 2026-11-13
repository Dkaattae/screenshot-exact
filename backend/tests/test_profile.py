from tests.conftest import PNG, jpeg


def body_files():
    return {"front": jpeg(), "side": jpeg(), "back": jpeg()}


def test_profile_is_empty_at_first(client, auth):
    assert client.get("/users/me/profile", headers=auth).json() == {"body": None}


def test_save_body_and_read_it_back(client, auth):
    response = client.put(
        "/users/me/body",
        headers=auth,
        files=body_files(),
        data={"consent": "true", "height_cm": "170", "measurements": '{"waist": 70, "hip": null}'},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["height_cm"] == 170
    assert body["measurements"] == {"waist": 70, "hip": None}
    assert set(body["images"]) == {"front", "side", "back"}
    assert client.get("/users/me/profile", headers=auth).json()["body"]["id"] == body["id"]


def test_save_body_requires_consent(client, auth):
    response = client.put(
        "/users/me/body", headers=auth, files=body_files(), data={"consent": "false"}
    )
    assert response.status_code == 400
    assert "consent" in response.json()["error"]["message"]


def test_save_body_requires_all_three_photos(client, auth):
    files = {"front": jpeg(), "side": jpeg()}
    response = client.put("/users/me/body", headers=auth, files=files, data={"consent": "true"})
    assert response.status_code == 400


def test_replacing_body_keeps_the_same_profile(client, auth):
    first = client.put("/users/me/body", headers=auth, files=body_files(), data={"consent": "true"})
    second = client.put(
        "/users/me/body", headers=auth, files=body_files(), data={"consent": "true"}
    )
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["images"]["front"] != second.json()["images"]["front"]


def test_delete_body(client, auth):
    client.put("/users/me/body", headers=auth, files=body_files(), data={"consent": "true"})
    assert client.delete("/users/me/body", headers=auth).status_code == 204
    assert client.get("/users/me/profile", headers=auth).json() == {"body": None}


def test_rejects_non_image_upload(client, auth):
    files = {**body_files(), "front": ("notes.txt", b"hello", "text/plain")}
    response = client.put("/users/me/body", headers=auth, files=files, data={"consent": "true"})
    assert response.status_code == 400
    assert "JPEG, PNG or WebP" in response.json()["error"]["message"]


def test_rejects_file_whose_bytes_do_not_match_its_type(client, auth):
    files = {**body_files(), "front": ("fake.jpg", PNG, "image/jpeg")}
    response = client.put("/users/me/body", headers=auth, files=files, data={"consent": "true"})
    assert response.status_code == 400
    assert "not a valid image" in response.json()["error"]["message"]


def test_rejects_oversized_upload(client, auth, settings):
    settings.max_upload_bytes = 32
    files = {**body_files(), "front": ("big.jpg", b"\xff\xd8\xff" + b"0" * 64, "image/jpeg")}
    response = client.put("/users/me/body", headers=auth, files=files, data={"consent": "true"})
    assert response.status_code == 400
    assert "larger than" in response.json()["error"]["message"]


def test_backgrounds_list_presets_and_uploads(client, auth):
    presets = client.get("/users/me/backgrounds", headers=auth).json()
    assert len(presets) == 3 and all(b["is_preset"] for b in presets)
    created = client.post(
        "/users/me/backgrounds", headers=auth, files={"file": jpeg()}, data={"name": "Beach"}
    )
    assert created.status_code == 201
    assert created.json()["is_preset"] is False
    names = [b["name"] for b in client.get("/users/me/backgrounds", headers=auth).json()]
    assert names[-1] == "Beach"


def test_uploaded_backgrounds_are_private(client, auth):
    from tests.conftest import register

    client.post("/users/me/backgrounds", headers=auth, files={"file": jpeg()}, data={"name": "Mine"})
    other = register(client, "other@example.com")
    names = [b["name"] for b in client.get("/users/me/backgrounds", headers=other).json()]
    assert "Mine" not in names
