import pytest
from sqlalchemy import select, text

from app.infrastructure.auth.fake_sso import TEST_USERS, issue_token
from app.infrastructure.db.models import Claim, Handover, VerificationMethod
from app.infrastructure.security.crypto import CryptoError, decrypt, encrypt


def test_roundtrip_including_unicode():
    for value in ["student001", "Айгерим Қасымова", "a@b.kz", ""]:
        assert decrypt(encrypt(value)) == value


def test_same_value_gives_different_ciphertext():
    assert encrypt("same") != encrypt("same")


def test_ciphertext_does_not_contain_plaintext():
    assert "secret-phone" not in encrypt("secret-phone")


def test_tampered_data_is_rejected():
    token = encrypt("hello")
    flipped = token[:-2] + ("A" if token[-2] != "A" else "B") + token[-1]
    with pytest.raises(CryptoError):
        decrypt(flipped)


def test_plain_value_is_rejected():
    with pytest.raises(CryptoError):
        decrypt("not encrypted")


def test_user_fields_are_ciphertext_in_db_but_plain_in_api(client, session_factory):
    token = issue_token(TEST_USERS["student"], "student", email="student@campus.edu")
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    # API возвращает расшифрованные данные
    assert response.json()["campus_id"] == "student001"
    assert response.json()["email"] == "student@campus.edu"

    # а в самой базе лежит шифртекст
    with session_factory() as session:
        row = session.execute(text("SELECT campus_id, email FROM users")).one()
    assert row.campus_id.startswith("v1:")
    assert row.email.startswith("v1:")
    assert "student001" not in row.campus_id
    assert "student@campus.edu" not in row.email


def test_claim_answers_and_student_id_are_encrypted(session_factory):
    answers = '{"1": "blue wallpaper"}'
    with session_factory() as session:
        session.add(Claim(found_item_id=1, claimant_id=1, answers=answers))
        session.add(
            Handover(
                claim_id=1,
                recipient_name="Aigerim",
                recipient_student_id="240107999",
                verification_method=VerificationMethod.student_id_in_person,
                issued_by_id=1,
            )
        )
        session.commit()

    with session_factory() as session:  # новая сессия: данные читаются из базы
        raw_answers = session.execute(text("SELECT answers FROM claims")).scalar_one()
        raw_student_id = session.execute(
            text("SELECT recipient_student_id FROM handovers")
        ).scalar_one()
        claim = session.scalar(select(Claim))
        handover = session.scalar(select(Handover))

    assert raw_answers.startswith("v1:") and "blue wallpaper" not in raw_answers
    assert raw_student_id.startswith("v1:") and "240107999" not in raw_student_id
    assert claim.answers == answers
    assert handover.recipient_student_id == "240107999"
