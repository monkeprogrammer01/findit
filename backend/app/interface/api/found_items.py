from datetime import date, datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.application import found_items as service
from app.application import matching
from app.application.notifications import Notifier, notify
from app.config import get_settings
from app.infrastructure.db.models import (
    CampusLocation,
    FoundItem,
    FoundItemStatus,
    ItemCategory,
    User,
    UserRole,
)
from app.infrastructure.notifications.gateway import get_notifier
from app.infrastructure.storage.photos import PhotoStore, get_photo_store
from app.interface.api.deps import CurrentUser, DbSession, DeskAdmin

router = APIRouter(prefix="/found-items", tags=["found-items"])

Photos = Annotated[PhotoStore, Depends(get_photo_store)]
Notifications = Annotated[Notifier, Depends(get_notifier)]
Text200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Text50 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Color = Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)]
SerialNumber = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
Description = Annotated[str, StringConstraints(max_length=2000)]
Answer = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class QuestionIn(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]
    answer: Answer


class FoundItemCreate(BaseModel):
    title: Text200
    category: ItemCategory
    found_date: date
    location: CampusLocation
    color: Color | None = None
    serial_number: SerialNumber | None = None
    description: Description | None = None
    storage_desk: Text50
    storage_cell: Text50
    questions: list[QuestionIn] = Field(min_length=1, max_length=5)

    @field_validator("found_date")
    @classmethod
    def _not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("found_date cannot be in the future")
        return value


class FoundItemPublic(BaseModel):
    """То, что видят все: без места хранения, серийного номера и секретных вопросов."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: ItemCategory
    found_date: date
    location: CampusLocation
    color: str | None
    description: str | None
    status: FoundItemStatus
    received_at: datetime
    photo_urls: list[str]


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str


class QuestionWithAnswer(QuestionOut):
    correct_answer: str


class FoundItemAdmin(FoundItemPublic):
    """Полная карточка для стойки: место хранения, серийный номер, вопросы с ответами."""

    serial_number: str | None
    storage_desk: str
    storage_cell: str
    created_by_id: int
    questions: list[QuestionWithAnswer]


class FoundItemPage(BaseModel):
    items: list[FoundItemPublic]
    total: int
    limit: int
    offset: int


class PhotoOut(BaseModel):
    name: str
    url: str


def photo_url(item_id: int, name: str) -> str:
    return f"/found-items/{item_id}/photos/{name}"


def to_public(item: FoundItem) -> FoundItemPublic:
    return FoundItemPublic(
        id=item.id,
        title=item.title,
        category=item.category,
        found_date=item.found_date,
        location=item.location,
        color=item.color,
        description=item.description,
        status=item.status,
        received_at=item.received_at,
        photo_urls=[photo_url(item.id, n) for n in item.photos],
    )


def to_admin(db: DbSession, item: FoundItem) -> FoundItemAdmin:
    return FoundItemAdmin(
        **to_public(item).model_dump(),
        serial_number=item.serial_number,
        storage_desk=item.storage_desk,
        storage_cell=item.storage_cell,
        created_by_id=item.created_by_id,
        questions=[
            QuestionWithAnswer(id=q.id, question=q.question, correct_answer=q.correct_answer)
            for q in service.get_questions(db, item.id)
        ],
    )


@router.post("", response_model=FoundItemAdmin, status_code=status.HTTP_201_CREATED)
def create_found_item(
    data: FoundItemCreate,
    admin: DeskAdmin,
    db: DbSession,
    background: BackgroundTasks,
    notifier: Notifications,
):
    fields = data.model_dump(exclude={"questions"})
    questions = [q.model_dump() for q in data.questions]
    item = service.create_item(db, admin.id, fields, questions)
    # FR-03: сразу ищем подходящие отчёты о потере и пишем их авторам
    for report, score in matching.match_found_item(db, item):
        author = db.get(User, report.author_id)
        notify(
            background,
            notifier,
            author,
            "match_found",
            report_title=report.title,
            item_title=item.title,
            score=score,
        )
    return to_admin(db, item)


@router.get("", response_model=FoundItemPage)
def search_found_items(
    user: CurrentUser,
    db: DbSession,
    q: Annotated[
        str | None, Query(max_length=100, description="Текст в названии или описании")
    ] = None,
    category: ItemCategory | None = None,
    location: CampusLocation | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    color: Annotated[str | None, Query(max_length=50)] = None,
    item_status: Annotated[
        FoundItemStatus | None, Query(alias="status", description="Только для сотрудников")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    if user.role == UserRole.student:
        statuses = service.VISIBLE_TO_STUDENTS
        if item_status is not None:
            statuses = tuple(s for s in statuses if s == item_status)
    else:
        statuses = (item_status,) if item_status else tuple(FoundItemStatus)
    items, total = service.search_items(
        db,
        statuses=statuses,
        category=category,
        location=location,
        date_from=date_from,
        date_to=date_to,
        color=color,
        text=q,
        limit=limit,
        offset=offset,
    )
    return FoundItemPage(
        items=[to_public(i) for i in items], total=total, limit=limit, offset=offset
    )


@router.get("/{item_id}", response_model=FoundItemPublic)
def read_found_item(item_id: int, user: CurrentUser, db: DbSession):
    return to_public(service.get_item(db, item_id))


@router.get("/{item_id}/full", response_model=FoundItemAdmin)
def read_found_item_full(item_id: int, admin: DeskAdmin, db: DbSession):
    return to_admin(db, service.get_item(db, item_id))


@router.get("/{item_id}/questions", response_model=list[QuestionOut])
def read_claim_questions(item_id: int, user: CurrentUser, db: DbSession):
    """Тексты вопросов для формы заявки. Правильные ответы сюда не попадают."""
    service.get_item(db, item_id)
    return service.get_questions(db, item_id)


@router.post("/{item_id}/photos", response_model=PhotoOut, status_code=status.HTTP_201_CREATED)
async def upload_photo(
    item_id: int,
    admin: DeskAdmin,
    db: DbSession,
    store: Photos,
    file: Annotated[UploadFile, File()],
):
    item = service.get_item(db, item_id)
    # читаем на 1 байт больше лимита: так узнаём, что файл слишком большой, не читая его целиком
    data = await file.read(get_settings().photo_max_bytes + 1)
    name = service.add_photo(db, store, item, data)
    return PhotoOut(name=name, url=photo_url(item.id, name))


@router.get("/{item_id}/photos/{name}")
def read_photo(item_id: int, name: str, user: CurrentUser, db: DbSession, store: Photos):
    item = service.get_item(db, item_id)
    data, content_type = service.read_photo(store, item, name)
    return Response(content=data, media_type=content_type)
