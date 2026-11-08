from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.application import lost_reports as service
from app.infrastructure.db.models import (
    CampusLocation,
    ItemCategory,
    LostReport,
    LostReportStatus,
    UserRole,
)
from app.interface.api.deps import CurrentUser, DbSession, forbid

router = APIRouter(prefix="/lost-reports", tags=["lost-reports"])

# Сотрудники могут читать чужие отчёты (для сопоставления), менять и удалять нельзя
STAFF_ROLES = (UserRole.desk_admin, UserRole.sys_admin)

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Color = Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)]
SerialNumber = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
Description = Annotated[str, StringConstraints(max_length=2000)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def _not_in_future(value: date | None) -> date | None:
    if value is not None and value > date.today():
        raise ValueError("lost_date cannot be in the future")
    return value


class LostReportCreate(BaseModel):
    title: Title
    category: ItemCategory
    lost_date: date
    location: CampusLocation
    color: Color | None = None
    serial_number: SerialNumber | None = None
    description: Description | None = None

    _check_date = field_validator("lost_date")(_not_in_future)


class LostReportUpdate(BaseModel):
    """Все поля необязательные: меняются только те, что прислал клиент."""

    title: Title | None = None
    category: ItemCategory | None = None
    lost_date: date | None = None
    location: CampusLocation | None = None
    color: Color | None = None
    serial_number: SerialNumber | None = None
    description: Description | None = None
    status: LostReportStatus | None = None

    _check_date = field_validator("lost_date")(_not_in_future)

    @field_validator("status")
    @classmethod
    def _only_open_or_closed(cls, value):
        # статус matched выставляет система при сопоставлении, не автор
        if value is not None and value not in (LostReportStatus.open, LostReportStatus.closed):
            raise ValueError("status can only be set to open or closed")
        return value

    @model_validator(mode="after")
    def _required_fields_not_null(self):
        for name in ("title", "category", "lost_date", "location", "status"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class LostReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: ItemCategory
    lost_date: date
    location: CampusLocation
    color: str | None
    serial_number: str | None
    description: str | None
    status: LostReportStatus
    author_id: int
    created_at: datetime


def _load(db: DbSession, report_id: int) -> LostReport:
    report = service.get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lost report not found")
    return report


@router.post("", response_model=LostReportOut, status_code=status.HTTP_201_CREATED)
def create_lost_report(data: LostReportCreate, user: CurrentUser, db: DbSession):
    return service.create_report(db, user.id, data.model_dump())


# /me объявлен раньше /{report_id}, иначе "me" попытались бы разобрать как число
@router.get("/me", response_model=list[LostReportOut])
def list_my_reports(user: CurrentUser, db: DbSession, limit: Limit = 50, offset: Offset = 0):
    return service.list_reports_by_author(db, user.id, limit, offset)


@router.get("/{report_id}", response_model=LostReportOut)
def read_lost_report(report_id: int, request: Request, user: CurrentUser, db: DbSession):
    report = _load(db, report_id)
    if report.author_id != user.id and user.role not in STAFF_ROLES:
        raise forbid(request, db, user, f"not the author of lost report {report_id}")
    return report


@router.patch("/{report_id}", response_model=LostReportOut)
def update_lost_report(
    report_id: int,
    data: LostReportUpdate,
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    report = _load(db, report_id)
    if report.author_id != user.id:
        raise forbid(request, db, user, f"not the author of lost report {report_id}")
    return service.update_report(db, report, data.model_dump(exclude_unset=True))


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lost_report(report_id: int, request: Request, user: CurrentUser, db: DbSession):
    report = _load(db, report_id)
    if report.author_id != user.id:
        raise forbid(request, db, user, f"not the author of lost report {report_id}")
    service.delete_report(db, report)
