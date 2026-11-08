"""Хранилище фото найденных вещей.

Сервис работает с интерфейсом PhotoStore. Сейчас фото лежат в папке
(в docker-compose это volume photos). Чтобы перейти на MinIO/S3, достаточно
написать ещё один класс с теми же тремя методами.
"""

from pathlib import Path
from typing import Protocol

from app.config import get_settings


class PhotoStore(Protocol):
    def save(self, key: str, data: bytes) -> None: ...

    def read(self, key: str) -> bytes | None: ...

    def total_size(self) -> int:
        """Сколько байт уже занято, нужно для лимита 10 ГБ (C-01)."""
        ...


class LocalPhotoStore:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        # ключ вида "../../etc/passwd" не должен выйти за пределы папки
        if not path.is_relative_to(self._root):
            raise ValueError("invalid photo key")
        return path

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, key: str) -> bytes | None:
        try:
            path = self._path(key)
        except ValueError:
            return None
        return path.read_bytes() if path.is_file() else None

    def total_size(self) -> int:
        return sum(p.stat().st_size for p in self._root.rglob("*") if p.is_file())


def get_photo_store() -> PhotoStore:
    """Зависимость FastAPI. В тестах подменяется на хранилище во временной папке."""
    return LocalPhotoStore(get_settings().photo_storage_dir)
