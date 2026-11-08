"""FR-03: балл совпадения между отчётом о потере и найденной вещью.

Чистая функция без базы данных и HTTP: её легко проверить тестами и поменять веса.

Правила:
- категория должна совпадать, иначе пары нет;
- вещь не могла быть найдена раньше, чем потеряна (допуск 1 день);
- точное совпадение серийного номера сразу даёт 1.0;
- иначе балл = база за категорию + место + близость дат + цвет + общие слова.
"""

import re
from dataclasses import dataclass
from datetime import date

WEIGHT_CATEGORY = 0.20
WEIGHT_LOCATION = 0.20
WEIGHT_DATE = 0.20
WEIGHT_COLOR = 0.15
WEIGHT_KEYWORDS = 0.25

DATE_WINDOW_DAYS = 14  # через 14 дней после потери близость дат уже ничего не даёт
EARLY_TOLERANCE_DAYS = 1  # дату потери студенты часто указывают неточно
MATCH_THRESHOLD = 0.5  # пары с меньшим баллом не сохраняем

_STOP_WORDS = {"a", "an", "the", "and", "or", "with", "in", "on", "of", "my", "for"}


@dataclass(frozen=True)
class ItemFacts:
    """Признаки вещи, общие для отчёта о потере и найденной вещи."""

    category: str
    location: str
    day: date
    color: str | None = None
    serial_number: str | None = None
    text: str = ""


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zа-яё0-9]+", text.lower()) if len(w) > 2} - _STOP_WORDS


def _same(a: str | None, b: str | None) -> bool:
    return bool(a and b and a.strip().lower() == b.strip().lower())


def match_score(lost: ItemFacts, found: ItemFacts) -> float:
    """Возвращает балл от 0 до 1. 0 значит, что пара невозможна."""
    if lost.category != found.category:
        return 0.0
    days_after_loss = (found.day - lost.day).days
    if days_after_loss < -EARLY_TOLERANCE_DAYS:
        return 0.0
    if _same(lost.serial_number, found.serial_number):
        return 1.0

    score = WEIGHT_CATEGORY
    if lost.location == found.location:
        score += WEIGHT_LOCATION
    closeness = 1 - max(days_after_loss, 0) / DATE_WINDOW_DAYS
    score += WEIGHT_DATE * max(closeness, 0)
    if _same(lost.color, found.color):
        score += WEIGHT_COLOR
    lost_words, found_words = _words(lost.text), _words(found.text)
    if lost_words and found_words:
        overlap = len(lost_words & found_words) / len(lost_words | found_words)
        score += WEIGHT_KEYWORDS * overlap
    return round(min(score, 1.0), 3)


def is_match(score: float) -> bool:
    return score >= MATCH_THRESHOLD
