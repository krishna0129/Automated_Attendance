"""
Storage backends for captured face images.

The backend is chosen with the FACE_IMAGE_STORAGE setting:

* ``filesystem`` – JPEGs under ``FACE_DATA_DIR/training_dataset/<username>/``
* ``database``   – rows in :class:`recognition.models.FaceImage`, i.e. in
  whatever database DATABASE_URL points at (e.g. PostgreSQL).

Both expose the same small interface so capture and training code do not
care where images live.
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured

from .models import FaceImage

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


@dataclass(frozen=True)
class StoredImage:
    username: str
    ref: str  # backend-specific identifier, passed back to delete()
    data: bytes  # encoded image bytes


class FaceImageStore(ABC):
    @abstractmethod
    def save(self, user: User, image: bytes) -> None:
        """Store one encoded (JPEG) face image for ``user``."""

    @abstractmethod
    def clear(self, user: User) -> None:
        """Remove every stored image of ``user``."""

    @abstractmethod
    def count(self, user: User) -> int:
        """Number of images stored for ``user``."""

    @abstractmethod
    def iter_images(self) -> Iterator[StoredImage]:
        """Yield every stored image of every user."""

    @abstractmethod
    def delete(self, ref: str) -> None:
        """Remove a single image previously yielded by :meth:`iter_images`."""


class FileSystemFaceStore(FaceImageStore):
    def __init__(self, root: Path):
        self.root = Path(root)

    def _user_dir(self, user: User) -> Path:
        return self.root / user.username

    def _files(self, directory: Path) -> list[Path]:
        if not directory.is_dir():
            return []
        return sorted(p for p in directory.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)

    def save(self, user: User, image: bytes) -> None:
        directory = self._user_dir(user)
        directory.mkdir(parents=True, exist_ok=True)
        next_index = 1 + max((int(p.stem) for p in self._files(directory) if p.stem.isdigit()), default=0)
        (directory / f"{next_index}.jpg").write_bytes(image)

    def clear(self, user: User) -> None:
        shutil.rmtree(self._user_dir(user), ignore_errors=True)

    def count(self, user: User) -> int:
        return len(self._files(self._user_dir(user)))

    def iter_images(self) -> Iterator[StoredImage]:
        if not self.root.is_dir():
            return
        for user_dir in sorted(p for p in self.root.iterdir() if p.is_dir()):
            for path in self._files(user_dir):
                yield StoredImage(username=user_dir.name, ref=str(path), data=path.read_bytes())

    def delete(self, ref: str) -> None:
        Path(ref).unlink(missing_ok=True)


class DatabaseFaceStore(FaceImageStore):
    def save(self, user: User, image: bytes) -> None:
        FaceImage.objects.create(user=user, image=image)

    def clear(self, user: User) -> None:
        FaceImage.objects.filter(user=user).delete()

    def count(self, user: User) -> int:
        return FaceImage.objects.filter(user=user).count()

    def iter_images(self) -> Iterator[StoredImage]:
        rows = FaceImage.objects.values_list("id", "user__username", "image").order_by("user_id", "id")
        for pk, username, data in rows.iterator(chunk_size=200):
            yield StoredImage(username=username, ref=str(pk), data=bytes(data))

    def delete(self, ref: str) -> None:
        FaceImage.objects.filter(pk=int(ref)).delete()


def training_dataset_dir() -> Path:
    return Path(settings.FACE_DATA_DIR) / "training_dataset"


def get_face_store(backend: str | None = None) -> FaceImageStore:
    backend = (backend or settings.FACE_IMAGE_STORAGE).lower()
    if backend == "filesystem":
        return FileSystemFaceStore(training_dataset_dir())
    if backend == "database":
        return DatabaseFaceStore()
    raise ImproperlyConfigured(
        f"Unknown FACE_IMAGE_STORAGE {backend!r}; expected 'filesystem' or 'database'."
    )
