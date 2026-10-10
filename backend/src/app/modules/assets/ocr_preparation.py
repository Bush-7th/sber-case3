"""PDF/image part of M03 preparation; Office converters remain a separate FMT01 adapter."""

from dataclasses import dataclass, field
from io import BytesIO
from threading import RLock
from uuid import uuid4

import PIL
import pypdfium2 as pdfium
from PIL import Image, UnidentifiedImageError

from app.modules.assets.ocr import OcrSource, PreparationFailure, PreparedOcrPage

# PDFium cannot execute concurrently even against different documents. Do not hold this during HTTP.
PDFIUM_LOCK = RLock()


@dataclass(frozen=True)
class PreparedPageContent:
    source: OcrSource
    page: int
    preparation_profile: str
    native_text: str | None = field(default=None, repr=False)
    ocr_page: PreparedOcrPage | None = None


def prepare_pdf(
    source: OcrSource, data: bytes, *, max_pages: int = 200
) -> list[PreparedPageContent]:
    profile = f"pdf-page-v1/pdfium-{pdfium.PYPDFIUM_INFO.version}/native-bounded"
    result = []
    try:
        with PDFIUM_LOCK, pdfium.PdfDocument(data) as original:
            if len(original) < 1 or len(original) > max_pages:
                raise PreparationFailure("preparation_unsupported_input", uuid4())
            for index in range(len(original)):
                page = original[index]
                textpage = None
                try:
                    textpage = page.get_textpage()
                    text = textpage.get_text_bounded()
                finally:
                    if textpage is not None:
                        textpage.close()
                    page.close()
                if text.strip():
                    result.append(
                        PreparedPageContent(
                            source,
                            index + 1,
                            profile,
                            native_text=text,
                        )
                    )
                    continue
                # Import this page; never infer page boundaries from a combined OCR response.
                with pdfium.PdfDocument.new() as single:
                    single.import_pages(original, pages=[index])
                    stream = BytesIO()
                    single.save(stream)
                    payload = PreparedOcrPage(
                        source, index + 1, "application/pdf", profile, stream.getvalue()
                    )
                result.append(PreparedPageContent(source, index + 1, profile, ocr_page=payload))
    except (pdfium.PdfiumError, ValueError):
        raise PreparationFailure("preparation_unsupported_input", uuid4()) from None
    return result


def prepare_image(source: OcrSource, data: bytes) -> list[PreparedPageContent]:
    try:
        with Image.open(BytesIO(data)) as image:
            kind = image.format
            if kind not in {"PNG", "JPEG"} or getattr(image, "n_frames", 1) != 1:
                raise PreparationFailure("preparation_unsupported_input", uuid4())
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise PreparationFailure("preparation_unsupported_input", uuid4()) from None
    # Original pixels/orientation are preserved; this stage claims no bounding boxes.
    profile = f"original-image-v1/pillow-{PIL.__version__}"
    page = PreparedOcrPage(source, 1, "image/png" if kind == "PNG" else "image/jpeg", profile, data)
    return [PreparedPageContent(source, 1, profile, ocr_page=page)]


def prepare_ocr_content(
    source: OcrSource,
    data: bytes,
    media_type: str,
    *,
    max_pages: int = 200,
    max_bytes: int = 50_000_000,
):
    if not data or len(data) > max_bytes:
        raise PreparationFailure(
            "preparation_input_too_large" if data else "preparation_unsupported_input", uuid4()
        )
    if media_type == "application/pdf":
        return prepare_pdf(source, data, max_pages=max_pages)
    if media_type in {"image/png", "image/jpeg"}:
        return prepare_image(source, data)
    raise PreparationFailure("preparation_unsupported_input", uuid4())


def rasterize_pdf_page(source: OcrSource, data: bytes, page_number: int) -> PreparedOcrPage:
    """Explicit diagnostic/preview conversion. Normal preparation still bypasses native text."""
    profile = f"pdf-raster-v1/pdfium-{pdfium.PYPDFIUM_INFO.version}/scale-2"
    try:
        with PDFIUM_LOCK, pdfium.PdfDocument(data) as document:
            if page_number < 1 or page_number > len(document):
                raise PreparationFailure("preparation_unsupported_input", uuid4())
            page = document[page_number - 1]
            bitmap = image = None
            try:
                bitmap = page.render(scale=2)
                image = bitmap.to_pil()
                stream = BytesIO()
                image.save(stream, format="PNG")
                return PreparedOcrPage(source, page_number, "image/png", profile, stream.getvalue())
            finally:
                if image is not None:
                    image.close()
                if bitmap is not None:
                    bitmap.close()
                page.close()
    except (pdfium.PdfiumError, ValueError, OSError):
        raise PreparationFailure("preparation_unsupported_input", uuid4()) from None
