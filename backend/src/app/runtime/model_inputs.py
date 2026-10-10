"""M15 diagnostic wiring to M03 originals and prepared contents; no model HTTP calls."""

import argparse
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select

from app.modules.assets.local_preparation import prepare_local_image
from app.modules.assets.ocr import OcrSource
from app.modules.assets.ocr_persistence import FileVersionRow, OcrResultRow, SqlOcrRepository
from app.modules.assets.ocr_preparation import prepare_ocr_content, rasterize_pdf_page
from app.modules.assets.persistence import PostgresBlobStore
from app.modules.assets.text_projection import project_ocr_text
from app.modules.recognition.facts import PageLocation
from app.modules.recognition.model import ModelRequest, PreparedSource
from app.runtime.container import AppContainer

MEDIA = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def register_original(
    container: AppContainer, data: bytes, media: str, version_id: UUID
) -> OcrSource:
    from hashlib import sha256

    digest = sha256(data).hexdigest()
    with container.unit_of_work() as uow:
        existing = uow.session.get(FileVersionRow, version_id)
        if existing:
            source = OcrSource(existing.file_id, version_id, existing.original_blob_id, digest)
            SqlOcrRepository(uow.session).validate_source(source)
            return source
        blob = PostgresBlobStore(uow.session).put_immutable(uuid4(), data, media)
        source = OcrSource(uuid4(), version_id, blob.id, blob.sha256)
        SqlOcrRepository(uow.session).register_source(source)
        uow.commit()
        return source


def positive_page(value: str) -> int:
    page = int(value)
    if page < 1:
        raise argparse.ArgumentTypeError("Page numbering starts at 1")
    return page


def load_input(
    container: AppContainer,
    version_id: UUID,
    *,
    ocr_result_id: UUID | None,
    page: int | None,
    local_images: bool = False,
    rasterize: bool = False,
) -> ModelRequest:
    # Only M03 owns these reads; this diagnostic is explicit wiring, not a domain repository.
    with container.unit_of_work() as uow:
        version = uow.session.get(FileVersionRow, version_id)
        if version is None:
            raise ValueError("Unknown source version")
        file_id, original_id = version.file_id, version.original_blob_id
        if ocr_result_id:
            row = uow.session.scalar(
                select(OcrResultRow).where(
                    OcrResultRow.id == ocr_result_id, OcrResultRow.file_version_id == version_id
                )
            )
            if row is None:
                raise ValueError("Unknown saved OCR result")
            projection = project_ocr_text(row.text)
            sources = (
                PreparedSource(
                    "source-1",
                    PageLocation(
                        kind="page", file_id=file_id, file_version_id=version_id, page=row.page
                    ),
                    projection.text,
                    "ocr",
                    row.id,
                    row.preparation_profile + "/" + projection.profile,
                ),
            )
            return ModelRequest(sources)
        store = PostgresBlobStore(uow.session)
        blob = store.head(original_id)
        with store.open(original_id) as stream:
            data = stream.read()
    if sha256(data).hexdigest() != blob.sha256:
        raise ValueError("Original integrity mismatch")
    from app.modules.assets.ocr import OcrSource

    source = OcrSource(file_id, version_id, original_id, blob.sha256)
    if rasterize:
        if not local_images or blob.media_type != "application/pdf" or page is None:
            raise ValueError("Local PDF rasterization requires an explicit page")
        image = rasterize_pdf_page(source, data, page)
        image = prepare_local_image(image, max_side=container.settings.local_image_max_side)
        return ModelRequest(
            (
                PreparedSource(
                    f"source-{page}",
                    PageLocation(
                        kind="page", file_id=file_id, file_version_id=version_id, page=page
                    ),
                    "",
                    "vision",
                    preparation_profile=image.preparation_profile,
                    image=image.data,
                    media_type=image.media_type,
                ),
            )
        )
    prepared = prepare_ocr_content(
        source,
        data,
        blob.media_type,
        max_pages=container.settings.ocr_preparation_max_pages,
        max_bytes=container.settings.olmocr_max_input_bytes,
    )
    if page is not None:
        if page < 1 or page > len(prepared):
            raise ValueError("Unknown page")
        prepared = [prepared[page - 1]]
    sources = []
    for item in prepared:
        if not item.native_text:
            if local_images and item.ocr_page:
                image = item.ocr_page
                if image.media_type == "application/pdf":
                    image = rasterize_pdf_page(source, data, item.page)
                image = prepare_local_image(image, max_side=container.settings.local_image_max_side)
                sources.append(
                    PreparedSource(
                        f"source-{item.page}",
                        PageLocation(
                            kind="page", file_id=file_id, file_version_id=version_id, page=item.page
                        ),
                        "",
                        "vision",
                        preparation_profile=image.preparation_profile,
                        image=image.data,
                        media_type=image.media_type,
                    )
                )
                continue
            # The diagnostic never triggers another OCR attempt or fabricates empty-page text.
            raise ValueError("Run OCR preparation first and select its saved result")
        sources.append(
            PreparedSource(
                f"source-{item.page}",
                PageLocation(
                    kind="page", file_id=file_id, file_version_id=version_id, page=item.page
                ),
                item.native_text,
                preparation_profile=item.preparation_profile + "/native-text-v1",
            )
        )
    return ModelRequest(tuple(sources))
