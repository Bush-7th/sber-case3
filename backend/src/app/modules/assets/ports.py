from dataclasses import dataclass
from io import BytesIO
from typing import Protocol
from uuid import UUID


class BlobNotFound(Exception):
    pass


class BlobConflict(Exception):
    pass


@dataclass(frozen=True)
class BlobRef:
    id: UUID
    sha256: str
    size_bytes: int
    media_type: str


class BlobStore(Protocol):
    """Internal port. HTTP controllers must authorize the owning resource first."""

    def put_immutable(self, blob_id: UUID, data: bytes, media_type: str) -> BlobRef: ...

    def head(self, blob_id: UUID) -> BlobRef: ...

    def open(self, blob_id: UUID) -> BytesIO: ...

    def retain(self, blob_id: UUID, resource_id: UUID) -> None: ...

    def release(self, blob_id: UUID, resource_id: UUID) -> None: ...

    def delete_unreferenced(self, blob_id: UUID) -> bool: ...
