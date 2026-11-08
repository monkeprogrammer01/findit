from fastapi import APIRouter

from app.infrastructure.auth.fake_sso import TEST_USERS, issue_token
from app.infrastructure.db.models import UserRole

router = APIRouter(prefix="/dev-sso", tags=["dev-sso (только local)"])


@router.post("/token")
def get_test_token(role: UserRole = UserRole.student):
    token = issue_token(TEST_USERS[role.value], role.value)
    return {"access_token": token, "token_type": "bearer"}
