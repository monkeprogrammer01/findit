"""BE-12: выдача вещи (FR-05)."""

import pytest
from sqlalchemy import select, text

from app.infrastructure.db.models import AuditLog
from tests.helpers import ADMIN, OTHER_STUDENT, STUDENT, create_found_item, headers
from tests.test_claims import submit


def handover_body(**overrides) -> dict:
    data = {
        "verification_method": "student_id_in_person",
        "recipient_name": "Yerkebulan Kenzhegali",
        "recipient_student_id": "student001",
    }
    data.update(overrides)
    return data


@pytest.fixture
def approved(client) -> dict:
    item = create_found_item(client)
    claim = submit(client, item["id"]).json()
    client.post(f"/claims/{claim['id']}/approve", headers=ADMIN)
    return {"item": item, "claim": claim}


def hand_over(client, claim_id: int, who=ADMIN, **overrides):
    return client.post(f"/claims/{claim_id}/handover", json=handover_body(**overrides), headers=who)


def test_handover_returns_item_closes_claim_and_is_audited(
    client, approved, session_factory, notifier
):
    response = hand_over(client, approved["claim"]["id"])
    assert response.status_code == 201
    body = response.json()
    assert body["item"]["status"] == "returned"
    assert body["verification_method"] == "student_id_in_person"

    claim = client.get(f"/claims/{approved['claim']['id']}", headers=ADMIN).json()
    assert claim["status"] == "returned"
    public = client.get(f"/found-items/{approved['item']['id']}", headers=STUDENT).json()
    assert public["status"] == "returned"
    assert "FindIt: item handed over" in notifier.to("student001@stu.sdu.edu.kz")

    with session_factory() as session:
        entries = list(session.scalars(select(AuditLog).where(AuditLog.action == "handover")))
        raw_id = session.execute(text("SELECT recipient_student_id FROM handovers")).scalar_one()
    assert len(entries) == 1
    assert f"claim={approved['claim']['id']}" in entries[0].details
    assert "student001" not in raw_id  # номер студенческого зашифрован (C-02)


def test_no_handover_without_approved_claim(client):
    item = create_found_item(client)
    claim = submit(client, item["id"]).json()
    response = hand_over(client, claim["id"])  # заявка ещё pending
    assert response.status_code == 409
    client.post(f"/claims/{claim['id']}/reject", headers=ADMIN)
    assert hand_over(client, claim["id"]).status_code == 409


def test_handover_only_to_the_approved_claimant(client, approved):
    response = hand_over(client, approved["claim"]["id"], recipient_student_id="student002")
    assert response.status_code == 409
    claim = client.get(f"/claims/{approved['claim']['id']}", headers=ADMIN).json()
    assert claim["status"] == "approved"  # ничего не изменилось


def test_item_cannot_be_handed_over_twice(client, approved):
    assert hand_over(client, approved["claim"]["id"]).status_code == 201
    assert hand_over(client, approved["claim"]["id"]).status_code == 409


def test_digital_token_method_is_recorded(client, approved):
    response = hand_over(client, approved["claim"]["id"], verification_method="digital_token")
    assert response.json()["verification_method"] == "digital_token"


@pytest.mark.parametrize(
    "bad",
    [{"verification_method": "trust_me"}, {"recipient_name": ""}, {"recipient_student_id": " "}],
)
def test_handover_validation(client, approved, bad):
    assert hand_over(client, approved["claim"]["id"], **bad).status_code == 422


def test_only_desk_admin_can_hand_over(client, approved):
    for who in (STUDENT, OTHER_STUDENT, headers("admin001", "sys_admin")):
        assert hand_over(client, approved["claim"]["id"], who=who).status_code == 403


def test_unknown_claim_is_404(client):
    assert hand_over(client, 999).status_code == 404
