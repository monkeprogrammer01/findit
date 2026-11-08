"""Общие функции для тестов: токены и создание найденных вещей."""

from datetime import date, timedelta

from app.infrastructure.auth.fake_sso import issue_token

YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


def headers(campus_id: str = "student001", role: str = "student") -> dict:
    token = issue_token(campus_id, role, email=f"{campus_id}@stu.sdu.edu.kz")
    return {"Authorization": f"Bearer {token}"}


ADMIN = headers("desk001", "desk_admin")
STUDENT = headers("student001")
OTHER_STUDENT = headers("student002")


def found_payload(**overrides) -> dict:
    data = {
        "title": "Black iPhone 13",
        "category": "electronics",
        "found_date": YESTERDAY,
        "location": "library",
        "color": "black",
        "serial_number": "SN-12345",
        "description": "Phone in a black case",
        "storage_desk": "Desk A",
        "storage_cell": "Locker 12",
        "questions": [
            {"question": "What is the lock-screen picture?", "answer": "A cat on a sofa"},
            {"question": "What sticker is on the case?", "answer": "Barcelona"},
        ],
    }
    data.update(overrides)
    return data


def create_found_item(client, **overrides) -> dict:
    response = client.post("/found-items", json=found_payload(**overrides), headers=ADMIN)
    assert response.status_code == 201, response.text
    return response.json()
