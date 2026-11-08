"""FR-02: каталогизация найденных вещей и загрузка фото."""

import uuid
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.application.errors import BusinessRuleError, NotFoundError, StorageLimitError
from app.config import get_settings
from app.infrastructure.db.models import (
    CampusLocation,
    FoundItem,
    FoundItemStatus,
    ItemCategory,
    VerificationQuestion,
)
from app.infrastructure.storage.photos import PhotoStore

# Тип файла определяем по первым байтам, а не по имени или Content-Type от клиента
_SIGNATURES = {
    b"\xff\xd8\xff": ("image/jpeg", "jpg"),
    b"\x89PNG\r\n\x1a\n": ("image/png", "png"),
}
CONTENT_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def detect_image(data: bytes) -> str | None:
    """Возвращает расширение (jpg, png, webp) или None, если это не картинка."""
    for signature, (_, ext) in _SIGNATURES.items():
        if data.startswith(signature):
            return ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def create_item(db: Session, admin_id: int, data: dict, questions: list[dict]) -> FoundItem:
    item = FoundItem(created_by_id=admin_id, photos=[], **data)
    db.add(item)
    db.flush()  # нужен item.id для вопросов
    for q in questions:
        db.add(
            VerificationQuestion(
                found_item_id=item.id, question=q["question"], correct_answer=q["answer"]
            )
        )
    db.commit()
    db.refresh(item)
    return item


def get_item(db: Session, item_id: int) -> FoundItem:
    item = db.get(FoundItem, item_id)
    if item is None:
        raise NotFoundError("Found item not found")
    return item


def get_questions(db: Session, item_id: int) -> list[VerificationQuestion]:
    stmt = (
        select(VerificationQuestion)
        .where(VerificationQuestion.found_item_id == item_id)
        .order_by(VerificationQuestion.id)
    )
    return list(db.scalars(stmt))


def add_photo(db: Session, store: PhotoStore, item: FoundItem, data: bytes) -> str:
    """Проверяет фото, сохраняет его в хранилище и добавляет имя файла к вещи."""
    settings = get_settings()
    ext = detect_image(data)
    if ext is None:
        raise BusinessRuleError("Only JPEG, PNG or WebP images are allowed")
    if len(data) > settings.photo_max_bytes:
        raise BusinessRuleError(f"Photo is larger than {settings.photo_max_bytes} bytes")
    if len(item.photos) >= settings.photos_per_item:
        raise BusinessRuleError(f"An item can have at most {settings.photos_per_item} photos")
    if store.total_size() + len(data) > settings.photo_storage_limit_bytes:
        raise StorageLimitError("Photo storage limit reached")

    name = f"{uuid.uuid4().hex}.{ext}"
    store.save(f"{item.id}/{name}", data)
    # новый список, а не append: иначе SQLAlchemy не заметит изменение JSON-колонки
    item.photos = [*item.photos, name]
    db.commit()
    db.refresh(item)
    return name


def read_photo(store: PhotoStore, item: FoundItem, name: str) -> tuple[bytes, str]:
    if name not in item.photos:
        raise NotFoundError("Photo not found")
    data = store.read(f"{item.id}/{name}")
    if data is None:
        raise NotFoundError("Photo not found")
    return data, CONTENT_TYPES[name.rsplit(".", 1)[-1]]


# Студенты видят только вещи, которые ещё можно забрать
VISIBLE_TO_STUDENTS = (FoundItemStatus.stored, FoundItemStatus.eligible_for_disposal)


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_items(
    db: Session,
    *,
    statuses: tuple[FoundItemStatus, ...],
    category: ItemCategory | None = None,
    location: CampusLocation | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    color: str | None = None,
    text: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[FoundItem], int]:
    """Поиск для атрибута качества 2. Фильтры по колонкам с индексами идут первыми."""
    conditions = [FoundItem.status.in_(statuses)]
    if category is not None:
        conditions.append(FoundItem.category == category)
    if location is not None:
        conditions.append(FoundItem.location == location)
    if date_from is not None:
        conditions.append(FoundItem.found_date >= date_from)
    if date_to is not None:
        conditions.append(FoundItem.found_date <= date_to)
    if color:
        conditions.append(func.lower(FoundItem.color) == color.strip().lower())
    if text and text.strip():
        pattern = f"%{_escape_like(text.strip())}%"
        conditions.append(
            or_(
                FoundItem.title.ilike(pattern, escape="\\"),
                FoundItem.description.ilike(pattern, escape="\\"),
            )
        )

    total = db.scalar(select(func.count()).select_from(FoundItem).where(*conditions))
    stmt = (
        select(FoundItem)
        .where(*conditions)
        .order_by(FoundItem.found_date.desc(), FoundItem.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt)), total or 0
