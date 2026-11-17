"""Decode supported raster images before publishing their original bytes."""
from io import BytesIO
from pathlib import Path
import time

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

from app.core.errors import AppError

# Decode the primary image and regular frames; do not expand auxiliary/depth
# images or embedded thumbnails. Exports always keep the original container.
register_heif_opener(thumbnails=False, depth_images=False, aux_images=False, decode_threads=2)

IMAGE_TYPES = {"JPEG": (".jpg", "image/jpeg"), "PNG": (".png", "image/png"),
               "WEBP": (".webp", "image/webp"), "GIF": (".gif", "image/gif"),
               "HEIF": (".heic", "image/heic")}
HEIF_MIMES = frozenset({"image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence"})
MAX_PIXELS = 40_000_000
MAX_FRAME_PIXELS = 100_000_000
MAX_PREVIEW_EDGE = 1600


def verify_image(source: Path | bytes, check_cancelled=lambda: None, timeout=30):
    """Return the detected suffix/MIME; never re-encode or trust an URL suffix."""
    started = time.monotonic()

    def check():
        check_cancelled()
        if time.monotonic() - started > timeout:
            raise AppError("VERIFY_TIMEOUT", "图片校验超时，请重试。", 504)

    def open_image():
        return Image.open(BytesIO(source) if isinstance(source, bytes) else source,
                          formats=list(IMAGE_TYPES))

    try:
        check()
        with open_image() as image:
            result = IMAGE_TYPES[image.format]
            if image.format == "HEIF" and image.get_format_mimetype() in {"image/heif", "image/heif-sequence"}:
                result = (".heif", "image/heif")
            if not 0 < image.width * image.height <= MAX_PIXELS:
                raise AppError("INVALID_MEDIA", "图片尺寸超过安全解码范围。", 422)
            image.verify()
        # verify() only checks structure for some formats; load every frame as well.
        with open_image() as image:
            pixels = 0
            frames = getattr(image, "n_frames", 1)
            if frames > 100:
                raise AppError("INVALID_MEDIA", "图片帧数超过安全解码范围。", 422)
            for index in range(frames):
                check()
                image.seek(index)
                pixels += image.width * image.height
                if image.width * image.height > MAX_PIXELS or pixels > MAX_FRAME_PIXELS:
                    raise AppError("INVALID_MEDIA", "图片尺寸超过安全解码范围。", 422)
                image.load()
        check()
        return result
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, RuntimeError, EOFError,
            Image.DecompressionBombError) as exc:
        raise AppError("INVALID_MEDIA", "图片无法完整解码，已清理不完整文件。", 422) from exc


def browser_preview(data: bytes, detected_mime: str, *, timeout=30):
    """Render an already verified HEIF primary image for browsers, leaving originals untouched."""
    if detected_mime not in HEIF_MIMES:
        return data, detected_mime
    deadline = time.monotonic() + timeout

    def check():
        if time.monotonic() >= deadline:
            raise AppError("PREVIEW_TIMEOUT", "图片预览超时，请重新解析。", 504)

    try:
        check()
        with Image.open(BytesIO(data), formats=["HEIF"]) as image:
            if not 0 < image.width * image.height <= MAX_PIXELS:
                raise AppError("INVALID_MEDIA", "图片尺寸超过安全解码范围。", 422)
            # libheif applies container rotation and resets EXIF orientation.
            # exif_transpose also handles any remaining ordinary EXIF rotation.
            image.load()
            check()
            oriented = ImageOps.exif_transpose(image)
            oriented.thumbnail((MAX_PREVIEW_EDGE, MAX_PREVIEW_EDGE), Image.Resampling.LANCZOS)
            if "A" in oriented.getbands():
                background = Image.new("RGB", oriented.size, "white")
                background.paste(oriented, mask=oriented.getchannel("A"))
                oriented = background
            else:
                oriented = oriented.convert("RGB")
            check()
            output = BytesIO()
            oriented.save(output, format="JPEG", quality=85)
            check()
            return output.getvalue(), "image/jpeg"
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, RuntimeError, EOFError,
            Image.DecompressionBombError) as exc:
        raise AppError("INVALID_MEDIA", "图片预览转换失败，请尝试直接导出原图。", 422) from exc
