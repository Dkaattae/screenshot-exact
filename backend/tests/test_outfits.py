from tests.conftest import add_item, register


def test_create_outfit_starts_at_version_1(outfit):
    assert outfit["version"] == 1
    assert outfit["favorite"] is False
    assert outfit["name"] is None


def test_top_mode_requires_a_bottom(client, auth, outfit_state):
    outfit_state["base"]["bottom_id"] = None
    response = client.post("/users/me/outfits", headers=auth, json={"state": outfit_state})
    assert response.status_code == 400
    assert "Choose a bottom." in response.json()["error"]["message"]


def test_one_piece_mode_needs_no_bottom(client, auth, outfit_state, wardrobe):
    outfit_state["base"] = {"mode": "one_piece", "one_piece_id": wardrobe["one_piece"]["id"]}
    response = client.post("/users/me/outfits", headers=auth, json={"state": outfit_state})
    assert response.status_code == 201, response.text


def test_items_must_match_their_slot(client, auth, outfit_state, wardrobe):
    outfit_state["base"]["top_id"] = wardrobe["bottom"]["id"]
    response = client.post("/users/me/outfits", headers=auth, json={"state": outfit_state})
    assert response.status_code == 400
    assert "not a top" in response.json()["error"]["message"]


def test_items_must_be_in_your_wardrobe(client, auth, outfit_state):
    other = register(client, "other@example.com")
    foreign = add_item(client, other, "top", "Their shirt")
    outfit_state["base"]["top_id"] = foreign["id"]
    response = client.post("/users/me/outfits", headers=auth, json={"state": outfit_state})
    assert response.status_code == 400
    assert "not in your wardrobe" in response.json()["error"]["message"]


def test_unknown_body_and_background_are_rejected(client, auth, outfit_state):
    outfit_state["body"] = {"kind": "default", "id": "nope"}
    outfit_state["background_id"] = "nope"
    response = client.post("/users/me/outfits", headers=auth, json={"state": outfit_state})
    message = response.json()["error"]["message"]
    assert "default body was not found" in message
    assert "background was not found" in message


def test_user_body_must_be_your_profile(client, auth, outfit_state):
    outfit_state["body"] = {"kind": "user", "id": "someone-else"}
    response = client.post("/users/me/outfits", headers=auth, json={"state": outfit_state})
    assert response.status_code == 400


def test_patch_state_bumps_version(client, auth, outfit):
    url = f"/users/me/outfits/{outfit['id']}"
    base = {**outfit["state"]["base"], "tucked": True}
    response = client.patch(url, headers=auth, json={"base": base})
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 2
    assert response.json()["state"]["base"]["tucked"] is True


def test_patch_name_or_favorite_keeps_version(client, auth, outfit):
    url = f"/users/me/outfits/{outfit['id']}"
    response = client.patch(url, headers=auth, json={"name": "Sunday", "favorite": True})
    assert response.json()["version"] == 1
    assert response.json()["name"] == "Sunday"
    assert response.json()["favorite"] is True


def test_patch_with_same_state_keeps_version(client, auth, outfit):
    url = f"/users/me/outfits/{outfit['id']}"
    response = client.patch(url, headers=auth, json={"outer": outfit["state"]["outer"]})
    assert response.json()["version"] == 1


def test_patch_can_remove_outer(client, auth, outfit):
    url = f"/users/me/outfits/{outfit['id']}"
    response = client.patch(url, headers=auth, json={"outer": None})
    assert response.json()["state"]["outer"] is None


def test_patch_rejects_empty_body_and_null_base(client, auth, outfit):
    url = f"/users/me/outfits/{outfit['id']}"
    assert client.patch(url, headers=auth, json={}).status_code == 400
    assert client.patch(url, headers=auth, json={"base": None}).status_code == 400


def test_edit_understood(client, auth, outfit):
    url = f"/users/me/outfits/{outfit['id']}/edit"
    tucked = client.post(url, headers=auth, json={"message": "tuck in the shirt"}).json()
    assert tucked["change_summary"] == "Shirt tucked in."
    assert tucked["outfit"]["version"] == 2
    opened = client.post(url, headers=auth, json={"message": "open the jacket"}).json()
    assert opened["outfit"]["state"]["outer"]["open"] is True


def test_edit_not_understood_changes_nothing(client, auth, outfit):
    url = f"/users/me/outfits/{outfit['id']}/edit"
    result = client.post(url, headers=auth, json={"message": "make it purple"}).json()
    assert "wasn't understood" in result["change_summary"]
    assert result["outfit"]["version"] == 1


def test_list_outfits_newest_first_and_delete(client, auth, outfit_state):
    first = client.post("/users/me/outfits", headers=auth, json={"state": outfit_state}).json()
    second = client.post("/users/me/outfits", headers=auth, json={"state": outfit_state}).json()
    ids = [o["id"] for o in client.get("/users/me/outfits", headers=auth).json()]
    assert ids == [second["id"], first["id"]]
    assert client.delete(f"/users/me/outfits/{first['id']}", headers=auth).status_code == 204
    assert client.get(f"/users/me/outfits/{first['id']}", headers=auth).status_code == 404


def test_other_users_outfits_are_not_found(client, outfit):
    other = register(client, "other@example.com")
    assert client.get(f"/users/me/outfits/{outfit['id']}", headers=other).status_code == 404
