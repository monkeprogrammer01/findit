"""BE-9: автоматическое сопоставление (FR-03)."""

import time
from datetime import date, timedelta

from app.domain.matching import ItemFacts, is_match, match_score
from tests.helpers import ADMIN, OTHER_STUDENT, STUDENT, create_found_item, headers

TODAY = date.today()


def facts(**overrides) -> ItemFacts:
    data = dict(
        category="electronics",
        location="library",
        day=TODAY - timedelta(days=2),
        color="black",
        serial_number=None,
        text="Black iPhone 13 in a case",
    )
    data.update(overrides)
    return ItemFacts(**data)


# ---- правила балла, без базы данных ----


def test_identical_items_score_high():
    assert match_score(facts(), facts()) >= 0.95


def test_different_category_never_matches():
    assert match_score(facts(), facts(category="keys")) == 0.0


def test_item_found_long_before_loss_cannot_match():
    assert match_score(facts(), facts(day=TODAY - timedelta(days=10))) == 0.0


def test_exact_serial_number_wins_even_if_other_fields_differ():
    lost = facts(serial_number="SN-1", location="parking", color="white", text="phone")
    found = facts(serial_number="sn-1 ", text="device")
    assert match_score(lost, found) == 1.0


def test_each_feature_adds_to_the_score():
    weak = facts(location="parking", color="white", text="something else entirely")
    base = match_score(facts(), weak)
    assert match_score(facts(), facts(color="white", text="something")) > base
    assert not is_match(base)


def test_closer_dates_give_higher_score():
    near = match_score(facts(), facts(day=TODAY - timedelta(days=1)))
    far = match_score(facts(), facts(day=TODAY + timedelta(days=10)))
    assert near > far


# ---- через API ----


def lost_report(client, who=STUDENT, **overrides) -> dict:
    data = {
        "title": "Black iPhone 13",
        "category": "electronics",
        "lost_date": (TODAY - timedelta(days=2)).isoformat(),
        "location": "library",
        "color": "black",
        "description": "Phone in a black case",
    }
    data.update(overrides)
    response = client.post("/lost-reports", json=data, headers=who)
    assert response.status_code == 201, response.text
    return response.json()


def test_new_found_item_is_matched_and_author_notified(client, notifier):
    report = lost_report(client)
    unrelated = lost_report(client, who=OTHER_STUDENT, title="Car keys", category="keys")

    item = create_found_item(client)

    matches = client.get(f"/lost-reports/{report['id']}/matches", headers=STUDENT).json()
    assert [m["found_item"]["id"] for m in matches] == [item["id"]]
    assert matches[0]["score"] >= 0.5
    assert "storage_cell" not in matches[0]["found_item"]
    assert client.get(f"/lost-reports/{report['id']}", headers=STUDENT).json()["status"] == (
        "matched"
    )
    assert (
        client.get(f"/lost-reports/{unrelated['id']}/matches", headers=OTHER_STUDENT).json() == []
    )
    assert notifier.to("student001@stu.sdu.edu.kz") == ["FindIt: possible match for your lost item"]
    assert notifier.to("student002@stu.sdu.edu.kz") == []


def test_report_filed_after_item_was_found_is_matched_too(client, notifier):
    item = create_found_item(client)
    report = lost_report(client)
    assert report["status"] == "matched"
    matches = client.get(f"/lost-reports/{report['id']}/matches", headers=STUDENT).json()
    assert matches[0]["found_item"]["id"] == item["id"]
    assert len(notifier.to("student001@stu.sdu.edu.kz")) == 1


def test_closed_reports_are_not_matched(client):
    report = lost_report(client)
    client.patch(f"/lost-reports/{report['id']}", json={"status": "closed"}, headers=STUDENT)
    create_found_item(client)
    assert client.get(f"/lost-reports/{report['id']}/matches", headers=STUDENT).json() == []


def test_best_match_comes_first(client):
    report = lost_report(client)
    weaker = create_found_item(client, location="parking", color="white", serial_number=None)
    stronger = create_found_item(client)
    matches = client.get(f"/lost-reports/{report['id']}/matches", headers=STUDENT).json()
    assert [m["found_item"]["id"] for m in matches] == [stronger["id"], weaker["id"]]


def test_other_student_cannot_see_matches_but_staff_can(client):
    report = lost_report(client)
    url = f"/lost-reports/{report['id']}/matches"
    assert client.get(url, headers=OTHER_STUDENT).status_code == 403
    assert client.get(url, headers=ADMIN).status_code == 200
    assert client.get(url, headers=headers("admin001", "sys_admin")).status_code == 200


def test_matching_200_open_reports_is_fast(client):
    """Цепочка из FR-03 должна укладываться в 60 с; здесь запас в сотни раз."""
    for i in range(200):
        lost_report(client, title=f"Black phone {i}")
    started = time.perf_counter()
    create_found_item(client)
    assert time.perf_counter() - started < 5
