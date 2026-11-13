from tests.conftest import add_item, jpeg, register


def test_create_item_with_and_without_back_photo(client, auth):
    shirt = add_item(client, auth, "top", "Shirt")
    jeans = add_item(client, auth, "bottom", "Jeans", back=False)
    assert shirt["back_url"] is not None
    assert jeans["back_url"] is None
    assert shirt["measurements"] == {"waist": 80}


def test_empty_back_file_part_counts_as_no_back_photo(client, auth):
    response = client.post(
        "/users/me/items",
        headers=auth,
        files={"front": jpeg(), "back": ("", b"", "application/octet-stream")},
        data={"slot": "top", "name": "Tee"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["back_url"] is None


def test_list_items_filters_by_slot(client, auth, wardrobe):
    tops = client.get("/users/me/items?slot=top", headers=auth).json()
    assert [i["name"] for i in tops] == ["Shirt"]
    assert len(client.get("/users/me/items", headers=auth).json()) == 5


def test_unknown_slot_is_rejected(client, auth):
    assert client.get("/users/me/items?slot=hat", headers=auth).status_code == 400


def test_create_item_requires_name_and_front(client, auth):
    no_name = client.post(
        "/users/me/items", headers=auth, files={"front": jpeg()}, data={"slot": "top", "name": " "}
    )
    no_front = client.post("/users/me/items", headers=auth, data={"slot": "top", "name": "Tee"})
    assert no_name.status_code == 400
    assert no_front.status_code == 400


def test_bad_measurements_are_rejected(client, auth):
    response = client.post(
        "/users/me/items",
        headers=auth,
        files={"front": jpeg()},
        data={"slot": "top", "name": "Tee", "measurements": '{"chest": "big"}'},
    )
    assert response.status_code == 400


def test_patch_item(client, auth):
    item = add_item(client, auth, "top", "Shirt")
    response = client.patch(
        f"/users/me/items/{item['id']}",
        headers=auth,
        json={"name": "Linen shirt", "measurements": {"chest": 100, "length": None}},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Linen shirt"
    assert response.json()["measurements"] == {"chest": 100, "length": None}
    assert response.json()["slot"] == "top"


def test_patch_rejects_null_name_and_unknown_fields(client, auth):
    item = add_item(client, auth, "top", "Shirt")
    url = f"/users/me/items/{item['id']}"
    assert client.patch(url, headers=auth, json={"name": None}).status_code == 400
    assert client.patch(url, headers=auth, json={"front_url": "x"}).status_code == 400


def test_delete_item(client, auth):
    item = add_item(client, auth, "top", "Shirt")
    assert client.delete(f"/users/me/items/{item['id']}", headers=auth).status_code == 204
    assert client.get("/users/me/items", headers=auth).json() == []


def test_other_users_items_are_not_found(client, auth):
    item = add_item(client, auth, "top", "Shirt")
    other = register(client, "other@example.com")
    url = f"/users/me/items/{item['id']}"
    assert client.patch(url, headers=other, json={"name": "Mine"}).status_code == 404
    assert client.delete(url, headers=other).status_code == 404
    assert client.get("/users/me/items", headers=other).json() == []
