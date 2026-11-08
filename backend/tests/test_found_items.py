"""BE-7: каталогизация найденных вещей и фото (FR-02)."""

import pytest

from app.config import get_settings
from tests.helpers import (
    ADMIN,
    STUDENT,
    YESTERDAY,
    create_found_item,
    found_payload,
    headers,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100


def upload(client, item_id: int, data: bytes, who: dict = ADMIN, name: str = "photo.png"):
    files = {"file": (name, data, "image/png")}
    return client.post(f"/found-items/{item_id}/photos", files=files, headers=who)


def test_desk_admin_catalogs_item_with_questions(client):
    item = create_found_item(client)
    assert item["status"] == "stored"
    assert item["storage_desk"] == "Desk A"
    assert item["storage_cell"] == "Locker 12"
    assert [q["correct_answer"] for q in item["questions"]] == ["A cat on a sofa", "Barcelona"]


def test_student_cannot_catalog(client):
    response = client.post("/found-items", json=found_payload(), headers=STUDENT)
    assert response.status_code == 403


@pytest.mark.parametrize(
    "bad",
    [
        {"questions": []},
        {"storage_desk": ""},
        {"category": "spaceship"},
        {"found_date": "2999-01-01"},
        {"questions": [{"question": "Q?", "answer": ""}]},
    ],
)
def test_catalog_validation(client, bad):
    response = client.post("/found-items", json=found_payload(**bad), headers=ADMIN)
    assert response.status_code == 422


def test_public_view_hides_storage_serial_and_questions(client):
    item = create_found_item(client)
    body = client.get(f"/found-items/{item['id']}", headers=STUDENT).json()
    for secret in ("storage_desk", "storage_cell", "serial_number", "questions"):
        assert secret not in body
    assert "A cat on a sofa" not in str(body)
    assert body["found_date"] == YESTERDAY


def test_claim_form_shows_questions_without_answers(client):
    item = create_found_item(client)
    questions = client.get(f"/found-items/{item['id']}/questions", headers=STUDENT).json()
    assert [q["question"] for q in questions] == [
        "What is the lock-screen picture?",
        "What sticker is on the case?",
    ]
    assert "correct_answer" not in questions[0]


def test_full_view_is_only_for_desk_admin(client):
    item = create_found_item(client)
    url = f"/found-items/{item['id']}/full"
    assert client.get(url, headers=STUDENT).status_code == 403
    assert client.get(url, headers=ADMIN).json()["storage_cell"] == "Locker 12"


def test_unknown_item_is_404(client):
    assert client.get("/found-items/999", headers=STUDENT).status_code == 404


def test_upload_photo_and_read_it_back(client):
    item = create_found_item(client)
    response = upload(client, item["id"], PNG)
    assert response.status_code == 201
    url = response.json()["url"]

    public = client.get(f"/found-items/{item['id']}", headers=STUDENT).json()
    assert public["photo_urls"] == [url]
    photo = client.get(url, headers=STUDENT)
    assert photo.status_code == 200
    assert photo.headers["content-type"] == "image/png"
    assert photo.content == PNG


def test_photo_type_is_checked_by_content_not_by_name(client):
    item = create_found_item(client)
    response = upload(client, item["id"], b"MZ\x90\x00 not an image", name="virus.png")
    assert response.status_code == 409
    assert upload(client, item["id"], JPEG, name="photo.jpg").status_code == 201


def test_photo_too_large_is_rejected(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "photo_max_bytes", 50)
    item = create_found_item(client)
    assert upload(client, item["id"], PNG).status_code == 409


def test_storage_limit_10gb_is_enforced(client, monkeypatch, photo_store):
    item = create_found_item(client)
    assert upload(client, item["id"], PNG).status_code == 201
    used = photo_store.total_size()
    monkeypatch.setattr(get_settings(), "photo_storage_limit_bytes", used + 10)
    response = upload(client, item["id"], PNG)
    assert response.status_code == 507
    assert photo_store.total_size() == used  # ничего не сохранили


def test_student_cannot_upload_photo(client):
    item = create_found_item(client)
    assert upload(client, item["id"], PNG, who=headers("student001")).status_code == 403


def test_unknown_photo_name_is_404(client):
    item = create_found_item(client)
    url = f"/found-items/{item['id']}/photos/..%2F..%2Fsecret.png"
    assert client.get(url, headers=STUDENT).status_code == 404
