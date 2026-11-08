"""BE-15: заполняет базу тестовыми найденными вещами.

Запуск из backend/:  python -m scripts.seed_found_items 20000
Тестовые записи помечены описанием '[seed] ...', перед вставкой старые удаляются.
"""

import random
import sys
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, insert, select

from app.infrastructure.db import models as m
from app.infrastructure.db.session import SessionLocal

SEED_MARK = "[seed]"
BATCH = 2000
TITLES = [
    "iPhone 13", "Samsung Galaxy", "AirPods", "House keys", "Wallet", "Backpack",
    "Student card", "Laptop charger", "Umbrella", "Water bottle", "Notebook",
    "Calculator", "Headphones", "Power bank", "Glasses", "Jacket", "Scarf",
    "USB flash drive", "MacBook", "Textbook",
]
COLORS = ["black", "white", "blue", "red", "gray", "green", "brown", "yellow"]


def build_rows(total: int, user_id: int) -> list[dict]:
    random.seed(42)
    categories = list(m.ItemCategory)
    locations = list(m.CampusLocation)
    now = datetime.now(UTC)
    rows = []
    for i in range(total):
        color = random.choice(COLORS)
        title = f"{color.capitalize()} {random.choice(TITLES)}"
        received = now - timedelta(days=random.randint(0, 80), hours=random.randint(0, 23))
        rows.append(
            {
                "title": title,
                "category": random.choice(categories),
                "found_date": (received.date() if received.date() <= date.today() else date.today()),
                "location": random.choice(locations),
                "color": color,
                "serial_number": f"SN-{random.randint(0, 99_999_999):08d}"
                if random.random() < 0.3
                else None,
                "description": f"{SEED_MARK} {title}, item number {i}",
                "storage_desk": random.choice(["Desk A", "Desk B"]),
                "storage_cell": f"Locker {random.randint(1, 60)}",
                "received_at": received,
                "created_by_id": user_id,
                "status": m.FoundItemStatus.stored,
            }
        )
    return rows


def main() -> None:
    total = int(sys.argv[1]) if len(sys.argv) > 1 else 20_000
    with SessionLocal() as db:
        user_id = db.scalar(select(m.User.id).order_by(m.User.id).limit(1))
        if user_id is None:
            sys.exit("В таблице users пусто: сначала один раз вызовите GET /me с токеном.")
        db.execute(delete(m.FoundItem).where(m.FoundItem.description.like(f"{SEED_MARK}%")))
        db.commit()
        rows = build_rows(total, user_id)
        for start in range(0, total, BATCH):
            db.execute(insert(m.FoundItem), rows[start : start + BATCH])
            db.commit()
            print(f"{min(start + BATCH, total)}/{total}")
        count = db.scalar(select(m.func.count(m.FoundItem.id))) if hasattr(m, "func") else None
        print("done", count if count is not None else "")


if __name__ == "__main__":
    main()
