import enum
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class UserRole(str, enum.Enum):
    student = "student"
    desk_admin = "desk_admin"
    sys_admin = "sys_admin"


class ItemCategory(str, enum.Enum):
    electronics = "electronics"
    documents = "documents"
    keys = "keys"
    wallet = "wallet"
    bag = "bag"
    clothing = "clothing"
    other = "other"


class CampusLocation(str, enum.Enum):
    library = "library"
    main_building = "main_building"
    dormitory = "dormitory"
    cafeteria = "cafeteria"
    sports_hall = "sports_hall"
    parking = "parking"
    other = "other"


class LostReportStatus(str, enum.Enum):
    open = "open"
    matched = "matched"
    closed = "closed"


class FoundItemStatus(str, enum.Enum):
    stored = "stored"
    claimed = "claimed"
    returned = "returned"
    eligible_for_disposal = "eligible_for_disposal"


class ClaimStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    returned = "returned"


class VerificationMethod(str, enum.Enum):
    student_id_in_person = "student_id_in_person"
    digital_token = "digital_token"


def _enum(enum_cls):
    """Enum хранится как текст (не как тип Postgres): проще менять в миграциях."""
    return Enum(
        enum_cls,
        native_enum=False,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )


def _now():
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # campus_id, email и phone станут зашифрованными в BE-5, поэтому длина с запасом
    campus_id: Mapped[str] = mapped_column(String(512))
    # хэш campus_id: по нему ищем пользователя при входе (шифртекст искать нельзя)
    campus_id_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    role: Mapped[UserRole] = mapped_column(_enum(UserRole), default=UserRole.student)
    email: Mapped[str | None] = mapped_column(String(512))
    phone: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = _now()


class LostReport(Base):
    __tablename__ = "lost_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[ItemCategory] = mapped_column(_enum(ItemCategory), index=True)
    lost_date: Mapped[date] = mapped_column(Date, index=True)
    location: Mapped[CampusLocation] = mapped_column(_enum(CampusLocation), index=True)
    color: Mapped[str | None] = mapped_column(String(50))
    serial_number: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[LostReportStatus] = mapped_column(
        _enum(LostReportStatus), default=LostReportStatus.open, index=True
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = _now()


class FoundItem(Base):
    __tablename__ = "found_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[ItemCategory] = mapped_column(_enum(ItemCategory), index=True)
    found_date: Mapped[date] = mapped_column(Date, index=True)
    location: Mapped[CampusLocation] = mapped_column(_enum(CampusLocation), index=True)
    color: Mapped[str | None] = mapped_column(String(50))
    serial_number: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    storage_desk: Mapped[str] = mapped_column(String(50))  # стойка, например "Desk A"
    storage_cell: Mapped[str] = mapped_column(String(50))  # ячейка, например "Locker 12"
    photos: Mapped[list] = mapped_column(JSON, default=list)  # пути к файлам в MinIO
    status: Mapped[FoundItemStatus] = mapped_column(
        _enum(FoundItemStatus), default=FoundItemStatus.stored, index=True
    )
    received_at: Mapped[datetime] = _now()  # дата поступления (для срока 90 дней)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class VerificationQuestion(Base):
    __tablename__ = "verification_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    found_item_id: Mapped[int] = mapped_column(
        ForeignKey("found_items.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(Text)
    correct_answer: Mapped[str] = mapped_column(Text)


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    found_item_id: Mapped[int] = mapped_column(ForeignKey("found_items.id"), index=True)
    claimant_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # ответы студента (JSON-строка), в BE-5 будут зашифрованы
    answers: Mapped[str] = mapped_column(Text)
    status: Mapped[ClaimStatus] = mapped_column(
        _enum(ClaimStatus), default=ClaimStatus.pending, index=True
    )
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now()


class Handover(Base):
    __tablename__ = "handovers"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), unique=True)
    recipient_name: Mapped[str] = mapped_column(String(200))
    # номер студенческого, в BE-5 будет зашифрован
    recipient_student_id: Mapped[str] = mapped_column(String(512))
    verification_method: Mapped[VerificationMethod] = mapped_column(_enum(VerificationMethod))
    issued_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    issued_at: Mapped[datetime] = _now()


class MatchSuggestion(Base):
    __tablename__ = "match_suggestions"
    __table_args__ = (UniqueConstraint("lost_report_id", "found_item_id", name="uq_match_pair"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lost_report_id: Mapped[int] = mapped_column(
        ForeignKey("lost_reports.id", ondelete="CASCADE"), index=True
    )
    found_item_id: Mapped[int] = mapped_column(
        ForeignKey("found_items.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = _now()


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100))  # например "forbidden", "handover"
    method: Mapped[str | None] = mapped_column(String(10))
    path: Mapped[str | None] = mapped_column(String(500))
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
