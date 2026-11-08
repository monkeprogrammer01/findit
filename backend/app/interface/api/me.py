from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from app.infrastructure.db.models import User, UserRole
from app.interface.api.deps import get_current_user

router = APIRouter(tags=["auth"])


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: str
    role: UserRole
    email: str | None


@router.get("/me", response_model=MeResponse)
def read_me(user: User = Depends(get_current_user)):
    return user
