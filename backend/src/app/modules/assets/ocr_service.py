import asyncio
from dataclasses import dataclass
from uuid import UUID

from app.modules.assets.ocr import (
    OcrPort,
    OcrProfile,
    OcrResult,
    OcrResultStore,
    PreparedOcrPage,
)


@dataclass(frozen=True)
class PreparedOcrResult:
    result: OcrResult
    reused: bool


class OcrContentService:
    """Caches derivative content, not a run verdict. Progress publication belongs to M10/M11."""

    def __init__(self, port: OcrPort, store: OcrResultStore):
        self.port = port
        self.store = store

    async def prepare(
        self, page: PreparedOcrPage, profile: OcrProfile, correlation_id: UUID
    ) -> PreparedOcrResult:
        cached = await asyncio.to_thread(self.store.find, page, profile)
        if cached is not None:
            return PreparedOcrResult(cached, reused=True)
        # Every store call closes its transaction before waiting on the remote service.
        output = await self.port.recognize(page, profile, correlation_id)
        result = await asyncio.to_thread(self.store.save, page, profile, output)
        return PreparedOcrResult(result, reused=False)
