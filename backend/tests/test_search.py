"""BE-8: поиск по найденным вещам (атрибут качества 2)."""

from datetime import date, timedelta

import pytest
from sqlalchemy import update

from app.infrastructure.db.models import FoundItem, FoundItemStatus
from tests.helpers import ADMIN, STUDENT, create_found_item


def days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


@pytest.fixture
def catalog(client):
    """Пять вещей с разными признаками."""
    return {
        "phone": create_found_item(client, title="Black iPhone", found_date=days_ago(1)),
        "keys": create_found_item(
            client,
            title="Car keys",
            category="keys",
            location="parking",
            color="silver",
            description="Toyota key with 50% discount card",
            found_date=days_ago(3),
        ),
        "wallet": create_found_item(
            client,
            title="Brown wallet",
            category="wallet",
            location="cafeteria",
            color="Brown",
            found_date=days_ago(10),
        ),
        "bag": create_found_item(
            client, title="Red bag", category="bag", color="red", found_date=days_ago(20)
        ),
        "laptop": create_found_item(
            client, title="Silver laptop", location="main_building", found_date=days_ago(5)
        ),
    }


def search(client, who=STUDENT, **params) -> dict:
    response = client.get("/found-items", params=params, headers=who)
    assert response.status_code == 200, response.text
    return response.json()


def titles(page: dict) -> list[str]:
    return [i["title"] for i in page["items"]]


def test_newest_first_with_total(client, catalog):
    page = search(client)
    assert page["total"] == 5
    assert titles(page) == ["Black iPhone", "Car keys", "Silver laptop", "Brown wallet", "Red bag"]


def test_filters_combine(client, catalog):
    assert titles(search(client, category="electronics")) == ["Black iPhone", "Silver laptop"]
    assert titles(search(client, category="electronics", location="main_building")) == [
        "Silver laptop"
    ]
    assert titles(search(client, color="brown")) == ["Brown wallet"]  # без учёта регистра


def test_date_range(client, catalog):
    page = search(client, date_from=days_ago(10), date_to=days_ago(3))
    assert titles(page) == ["Car keys", "Silver laptop", "Brown wallet"]


def test_text_search_in_title_and_description(client, catalog):
    assert titles(search(client, q="WALLET")) == ["Brown wallet"]
    assert titles(search(client, q="toyota")) == ["Car keys"]
    # % в запросе ищется как обычный символ, а не как шаблон
    assert titles(search(client, q="50%")) == ["Car keys"]
    assert search(client, q="%")["total"] == 1


def test_pagination(client, catalog):
    first = search(client, limit=2)
    second = search(client, limit=2, offset=2)
    assert first["total"] == second["total"] == 5
    assert titles(first) + titles(second) == [
        "Black iPhone",
        "Car keys",
        "Silver laptop",
        "Brown wallet",
    ]


def test_students_do_not_see_returned_items_but_staff_do(client, catalog, session_factory):
    with session_factory() as session:
        session.execute(
            update(FoundItem)
            .where(FoundItem.id == catalog["bag"]["id"])
            .values(status=FoundItemStatus.returned)
        )
        session.commit()
    assert "Red bag" not in titles(search(client))
    assert search(client, status="returned")["total"] == 0
    assert titles(search(client, who=ADMIN, status="returned")) == ["Red bag"]
    assert search(client, who=ADMIN)["total"] == 5


def test_results_never_contain_secret_fields(client, catalog):
    item = search(client)["items"][0]
    for secret in ("storage_desk", "storage_cell", "serial_number", "questions"):
        assert secret not in item


@pytest.mark.parametrize(
    "bad",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"category": "spaceship"},
        {"date_from": days_ago(1), "date_to": days_ago(5)},
    ],
)
def test_bad_parameters_are_422(client, bad):
    assert client.get("/found-items", params=bad, headers=STUDENT).status_code == 422


def test_search_requires_login(client):
    assert client.get("/found-items").status_code == 401
