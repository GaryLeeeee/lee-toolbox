import http.client
import socket
import time
from pathlib import Path

from app.core.errors import AppError
from app.core.security import open_media


def download_media(media_format, headers, destination: Path, store, task_id, settings, check_cancelled):
    if media_format.size_bytes and media_format.size_bytes > settings.max_download_bytes:
        raise AppError("FILE_TOO_LARGE", "视频超过单文件 2 GB 限制。", 413)
    start = time.monotonic()
    last_error = None
    for url in media_format.urls[:3]:
        check_cancelled()
        if time.monotonic() - start > settings.download_timeout:
            raise AppError("DOWNLOAD_TIMEOUT", "视频下载超时，请重试。", 504)
        response = connection = None
        destination.unlink(missing_ok=True)
        try:
            response, connection = open_media(url, headers, timeout=settings.network_timeout)
            if response.status != 200:
                raise AppError("DOWNLOAD_HTTP_ERROR", f"视频服务器返回 {response.status}，请重新解析或稍后重试。", 502)
            content_type = (response.getheader("Content-Type") or "").lower()
            if content_type and not (content_type.startswith("video/") or "octet-stream" in content_type or "mp4" in content_type):
                raise AppError("INVALID_MEDIA", "服务器未返回视频文件，请重新解析。", 502)
            length = response.getheader("Content-Length")
            total = int(length) if length and length.isdigit() else None
            if total and total > settings.max_download_bytes:
                raise AppError("FILE_TOO_LARGE", "视频超过单文件 2 GB 限制。", 413)
            received, last_update, last_bytes = 0, time.monotonic(), 0
            store.update(task_id, status="downloading", progress=5, total_bytes=total, downloaded_bytes=0)
            with destination.open("wb") as output:
                while True:
                    check_cancelled()
                    if time.monotonic() - start > settings.download_timeout:
                        raise AppError("DOWNLOAD_TIMEOUT", "视频下载超时，请重试。", 504)
                    chunk = response.read1(128 * 1024)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > settings.max_download_bytes:
                        raise AppError("FILE_TOO_LARGE", "视频超过单文件 2 GB 限制。", 413)
                    output.write(chunk)
                    current = time.monotonic()
                    if current - last_update >= 0.4:
                        progress = min(90, 5 + 85 * received / total) if total else 5
                        store.update(task_id, progress=progress, downloaded_bytes=received,
                                     speed_bps=(received - last_bytes) / (current - last_update))
                        last_update, last_bytes = current, received
            check_cancelled()
            if not received or (total is not None and received != total):
                raise AppError("INCOMPLETE_DOWNLOAD", "视频下载不完整，请重试。", 502)
            store.update(task_id, progress=90, downloaded_bytes=received, total_bytes=total or received, speed_bps=None)
            return received
        except AppError as exc:
            last_error = exc
            if exc.code in {"UNSAFE_URL", "FILE_TOO_LARGE", "DOWNLOAD_TIMEOUT"}:
                raise
        except (OSError, socket.timeout, http.client.HTTPException) as exc:
            last_error = AppError("NETWORK_ERROR", "视频下载网络异常，请检查网络后重试。", 502)
        finally:
            if response:
                response.close()
            if connection:
                connection.close()
    raise last_error or AppError("NO_MEDIA_URL", "没有可用的视频地址。", 422)
