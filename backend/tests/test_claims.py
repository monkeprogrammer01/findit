"""BE-10: заявки на найденные вещи (FR-04) и правила State pattern."""

import pytest
from sqlalchemy import text

from app.domain.claim_states import InvalidTransition, state_for
from tests.helpers import ADMIN, OTHER_STUDENT, STUDENT, create_found_item, headers

RIGHT = ["A cat on a sofa", "Barcelona"]


def answers_for(client, item_id: int, values=RIGHT) -> dict:
    questions = client.get(f"/found-items/{item_id}/questions", headers=STUDENT).json()
    return {
        "answers": [
            {"question_id": q["id"], "answer": v} for q, v in zip(questions, values, strict=True)
        ]
    }


def submit(client, item_id: int, who=STUDENT, values=RIGHT):
    return client.post(
        f"/found-items/{item_id}/claims", json=answers_for(client, item_id, values), headers=who
    )


@pytest.fixture
def item(client) -> dict:
    return create_found_item(client)


# ---- State pattern без базы данных ----


def test_state_rules():
    assert state_for("pending").approve().item_status == "claimed"
    assert state_for("pending").approve().reject_other_pending is True
    assert state_for("pending").reject().claim_status == "rejected"
    assert state_for("approved").hand_over().item_status == "returned"
    for status, action in [
        ("approved", "approve"),
        ("approved", "reject"),
        ("rejected", "approve"),
        ("rejected", "hand_over"),
        ("returned", "hand_over"),
        ("pending", "hand_over"),
    ]:
        with pytest.raises(InvalidTransition):
            getattr(state_for(status), action)()


# ---- успешный путь ----


def test_student_submits_claim_and_sees_it(client, item):
    response = submit(client, item["id"])
    assert response.status_code == 201
    claim = response.json()
    assert claim["status"] == "pending"
    assert claim["pickup"] is None
    assert sorted(claim["my_answers"].values()) == sorted(RIGHT)

    mine = client.get("/claims/me", headers=STUDENT).json()
    assert [c["id"] for c in mine] == [claim["id"]]
    assert client.get("/claims/me", headers=OTHER_STUDENT).json() == []


def test_admin_sees_answers_next_to_correct_ones(client, item):
    claim = submit(client, item["id"], values=["A dog", "Barcelona"]).json()
    detail = client.get(f"/claims/{claim['id']}", headers=ADMIN).json()
    assert detail["claimant_campus_id"] == "student001"
    assert detail["storage_cell"] == "Locker 12"
    pairs = [(a["correct_answer"], a["claimant_answer"]) for a in detail["answers"]]
    assert pairs == [("A cat on a sofa", "A dog"), ("Barcelona", "Barcelona")]


def test_approve_reserves_item_rejects_others_and_notifies(client, item, notifier):
    mine = submit(client, item["id"]).json()
    theirs = submit(client, item["id"], who=OTHER_STUDENT).json()

    response = client.post(f"/claims/{mine['id']}/approve", headers=ADMIN)
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["item"]["status"] == "claimed"

    other = client.get(f"/claims/{theirs['id']}", headers=ADMIN).json()
    assert other["status"] == "rejected"
    assert notifier.to("student001@stu.sdu.edu.kz") == ["FindIt: your claim was approved"]
    assert notifier.to("student002@stu.sdu.edu.kz") == ["FindIt: your claim was rejected"]

    pickup = client.get("/claims/me", headers=STUDENT).json()[0]["pickup"]
    assert pickup["storage_desk"] == "Desk A"
    assert "student ID" in pickup["instructions"]


def test_reject_keeps_item_available(client, item, notifier):
    claim = submit(client, item["id"]).json()
    response = client.post(f"/claims/{claim['id']}/reject", headers=ADMIN)
    assert response.json()["status"] == "rejected"
    assert client.get(f"/found-items/{item['id']}", headers=STUDENT).json()["status"] == "stored"
    assert notifier.to("student001@stu.sdu.edu.kz") == ["FindIt: your claim was rejected"]


def test_queue_filters_by_status_oldest_first(client, item):
    first = submit(client, item["id"]).json()
    second = submit(client, item["id"], who=OTHER_STUDENT).json()
    client.post(f"/claims/{first['id']}/reject", headers=ADMIN)
    queue = client.get("/claims", params={"status": "pending"}, headers=ADMIN).json()
    assert [c["id"] for c in queue] == [second["id"]]
    everything = client.get("/claims", headers=ADMIN).json()
    assert [c["id"] for c in everything] == [first["id"], second["id"]]


# ---- ошибки и бизнес-правила ----


def test_claim_on_unknown_item_is_404(client):
    body = {"answers": [{"question_id": 1, "answer": "x"}]}
    assert client.post("/found-items/999/claims", json=body, headers=STUDENT).status_code == 404


def test_all_questions_must_be_answered(client, item):
    full = answers_for(client, item["id"])
    partial = {"answers": full["answers"][:1]}
    url = f"/found-items/{item['id']}/claims"
    assert client.post(url, json=partial, headers=STUDENT).status_code == 409
    duplicate = {"answers": [full["answers"][0], full["answers"][0]]}
    assert client.post(url, json=duplicate, headers=STUDENT).status_code == 409
    empty = {"answers": [{"question_id": full["answers"][0]["question_id"], "answer": "  "}]}
    assert client.post(url, json=empty, headers=STUDENT).status_code == 422


def test_one_pending_claim_per_student(client, item):
    assert submit(client, item["id"]).status_code == 201
    assert submit(client, item["id"]).status_code == 409


def test_no_second_try_after_rejection(client, item):
    claim = submit(client, item["id"]).json()
    client.post(f"/claims/{claim['id']}/reject", headers=ADMIN)
    response = submit(client, item["id"])
    assert response.status_code == 409
    assert "rejected" in response.json()["detail"]


def test_claimed_item_accepts_no_new_claims(client, item):
    claim = submit(client, item["id"]).json()
    client.post(f"/claims/{claim['id']}/approve", headers=ADMIN)
    assert submit(client, item["id"], who=OTHER_STUDENT).status_code == 409
    assert client.post(f"/claims/{claim['id']}/approve", headers=ADMIN).status_code == 409
    assert client.post(f"/claims/{claim['id']}/reject", headers=ADMIN).status_code == 409


def test_students_cannot_review_or_read_other_answers(client, item):
    claim = submit(client, item["id"]).json()
    for who in (STUDENT, OTHER_STUDENT, headers("admin001", "sys_admin")):
        assert client.get(f"/claims/{claim['id']}", headers=who).status_code == 403
        assert client.get("/claims", headers=who).status_code == 403
        assert client.post(f"/claims/{claim['id']}/approve", headers=who).status_code == 403
    assert client.get("/claims/me", headers=OTHER_STUDENT).json() == []


def test_answers_are_encrypted_in_database(client, item, session_factory):
    submit(client, item["id"])
    with session_factory() as session:
        raw = session.execute(text("SELECT answers FROM claims")).scalar_one()
    assert raw.startswith("v1:")
    assert "Barcelona" not in raw
