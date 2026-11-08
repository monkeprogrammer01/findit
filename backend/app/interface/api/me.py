from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.infrastructure.db.models import UserRole
from app.interface.api.deps import CurrentUser

router = APIRouter(tags=["auth"])


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: str
    role: UserRole
    email: str | None


@router.get("/me", response_model=MeResponse)
def read_me(user: CurrentUser):
    return user
