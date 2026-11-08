from fastapi import APIRouter

from app.infrastructure.auth.fake_sso import TEST_USERS, issue_token
from app.infrastructure.db.models import UserRole

router = APIRouter(prefix="/dev-sso", tags=["dev-sso (только local)"])


@router.post("/token")
def get_test_token(role: UserRole = UserRole.student):
    campus_id = TEST_USERS[role.value]
    # тестовый email, чтобы письма из BE-11 было видно в MailHog
    token = issue_token(campus_id, role.value, email=f"{campus_id}@stu.sdu.edu.kz")
    return {"access_token": token, "token_type": "bearer"}
