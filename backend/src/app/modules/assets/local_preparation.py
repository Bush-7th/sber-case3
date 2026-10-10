"""M03 bounded image preparation for CPU vision, preserving original/page provenance."""

from dataclasses import replace
from io import BytesIO
from uuid import uuid4

import PIL
from PIL import Image, ImageOps, UnidentifiedImageError

from app.modules.assets.ocr import PreparationFailure, PreparedOcrPage


def prepare_local_image(page: PreparedOcrPage, *, max_side: int) -> PreparedOcrPage:
    if max_side < 256 or page.media_type not in {"image/png", "image/jpeg"}:
        raise PreparationFailure("preparation_unsupported_input", uuid4())
    try:
        with Image.open(BytesIO(page.data)) as original:
            if getattr(original, "n_frames", 1) != 1:
                raise ValueError("Animated images are unsupported")
            oriented = ImageOps.exif_transpose(original)
            if "A" in oriented.getbands() or "transparency" in oriented.info:
                rgba = oriented.convert("RGBA")
                image = Image.new("RGB", rgba.size, "white")
                image.paste(rgba, mask=rgba.getchannel("A"))
                rgba.close()
            else:
                image = oriented.convert("RGB")
            oriented.close()
            try:
                image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
                stream = BytesIO()
                image.save(stream, format="PNG")
            finally:
                image.close()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise PreparationFailure("preparation_unsupported_input", uuid4()) from None
    return replace(
        page,
        data=stream.getvalue(),
        media_type="image/png",
        preparation_profile=page.preparation_profile
        + f"/local-image-v1/max-side-{max_side}/pillow-{PIL.__version__}",
    )
