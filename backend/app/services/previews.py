"""Short-lived opaque references to bounded, verified public image previews."""
from collections import OrderedDict
from dataclasses import dataclass
import http.client
import secrets
import threading
import time

from app.core.errors import AppError
from app.core.security import open_media
from app.services.images import HEIF_MIMES, IMAGE_TYPES, browser_preview, verify_image

MAX_PREVIEW_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class Preview:
    urls: tuple[str, ...]
    headers: dict[str, str]
    expires_at: float


class PreviewRegistry:
    def __init__(self, *, ttl=600, capacity=256):
        self.ttl = ttl
        self.capacity = capacity
        self._entries = OrderedDict()
        self._lock = threading.Lock()

    def _prune(self):
        current = time.monotonic()
        for token in [key for key, value in self._entries.items() if value.expires_at <= current]:
            del self._entries[token]

    def register(self, urls, headers):
        if not urls:
            return None
        with self._lock:
            self._prune()
            while len(self._entries) >= self.capacity:
                self._entries.popitem(last=False)
            token = secrets.token_urlsafe(32)
            self._entries[token] = Preview(tuple(urls[:3]), dict(headers), time.monotonic() + self.ttl)
        return "/api/xhs/previews/" + token

    def get(self, token):
        with self._lock:
            self._prune()
            preview = self._entries.get(token)
        if preview is None:
            raise AppError("PREVIEW_EXPIRED", "预览已过期，请重新解析笔记。", 404)
        return preview


def fetch_preview(preview: Preview):
    deadline = time.monotonic() + 30
    error = None
    for url in preview.urls:
        response = connection = None
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AppError("PREVIEW_TIMEOUT", "图片预览超时，请重新解析。", 504)
            response, connection = open_media(url, preview.headers, timeout=min(10, remaining))
            if response.status != 200:
                raise AppError("PREVIEW_UNAVAILABLE", "图片预览暂不可用。", 502)
            mime = (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
            if mime not in {item[1] for item in IMAGE_TYPES.values()} | HEIF_MIMES:
                raise AppError("INVALID_MEDIA", "预览地址没有返回支持的图片。", 422)
            length = response.getheader("Content-Length")
            total = int(length) if length and length.isdigit() else None
            if total is not None and total > MAX_PREVIEW_BYTES:
                raise AppError("PREVIEW_TOO_LARGE", "图片超过 8 MB 预览限制，可尝试直接导出。", 413)
            output = bytearray()
            while True:
                if time.monotonic() >= deadline:
                    raise AppError("PREVIEW_TIMEOUT", "图片预览超时，请重新解析。", 504)
                chunk = response.read1(min(128 * 1024, MAX_PREVIEW_BYTES + 1 - len(output)))
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > MAX_PREVIEW_BYTES:
                    raise AppError("PREVIEW_TOO_LARGE", "图片超过 8 MB 预览限制，可尝试直接导出。", 413)
            if not output or (total is not None and total != len(output)):
                raise AppError("INCOMPLETE_DOWNLOAD", "图片预览下载不完整。", 502)
            data = bytes(output)
            _, detected_mime = verify_image(data, timeout=max(0, deadline - time.monotonic()))
            if detected_mime != mime and not (detected_mime in HEIF_MIMES and mime in HEIF_MIMES):
                raise AppError("INVALID_MEDIA", "图片预览类型不匹配。", 422)
            data, detected_mime = browser_preview(data, detected_mime, timeout=max(0, deadline - time.monotonic()))
            if len(data) > MAX_PREVIEW_BYTES:
                raise AppError("PREVIEW_TOO_LARGE", "图片超过 8 MB 预览限制，可尝试直接导出。", 413)
            if time.monotonic() >= deadline:
                raise AppError("PREVIEW_TIMEOUT", "图片预览超时，请重新解析。", 504)
            return data, detected_mime
        except AppError as exc:
            error = exc
            if exc.code in {"UNSAFE_URL", "PREVIEW_TOO_LARGE", "PREVIEW_TIMEOUT", "VERIFY_TIMEOUT"}:
                raise
        except (OSError, http.client.HTTPException):
            error = AppError("PREVIEW_UNAVAILABLE", "图片预览网络异常，请稍后重试。", 502)
        finally:
            if response:
                response.close()
            if connection:
                connection.close()
    raise error or AppError("PREVIEW_UNAVAILABLE", "图片预览暂不可用。", 502)
