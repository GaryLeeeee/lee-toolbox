"""All-or-nothing Xiaohongshu image and MP4 exports."""
import http.client
import json
from pathlib import Path
import shutil
import time
from zipfile import ZipFile, ZIP_STORED

from app.core.errors import AppError
from app.core.security import open_media
from app.services.files import safe_filename
from app.services.images import verify_image
from app.services.media import verify_media


def select_assets(note, asset_ids):
    assets = {asset.id: asset for asset in note.assets}
    if len(assets) != len(note.assets):
        raise AppError("INVALID_NOTE", "笔记资源编号重复，请重新解析。", 422)
    selected_ids = asset_ids if asset_ids is not None else [asset.id for asset in note.assets if asset.available]
    if not selected_ids or len(selected_ids) > 100 or len(set(selected_ids)) != len(selected_ids):
        raise AppError("INVALID_SELECTION", "请选择 1 至 100 个不同的可用资源。", 422)
    selected = []
    for asset_id in selected_ids:
        asset = assets.get(asset_id)
        if asset is None:
            raise AppError("ASSET_UNAVAILABLE", "所选资源已变化，请重新解析并选择。", 409)
        if not asset.available:
            raise AppError("ASSET_UNAVAILABLE", asset.unavailable_reason or "所选资源暂不可导出。", 422)
        if asset.kind not in {"image", "video"}:
            raise AppError("UNSUPPORTED_MEDIA", "暂不支持直接导出 Live Photo，请重新解析并选择图片或视频。", 422)
        if asset.kind == "image" and not asset.image_urls:
            raise AppError("IMAGE_UNAVAILABLE", "所选资源缺少原始图片，无法完整导出。", 422)
        if asset.kind == "video" and not asset.video_urls:
            raise AppError("VIDEO_UNAVAILABLE",
                           "所选资源缺少动态视频，无法完整导出。", 422)
        selected.append(asset)
    return selected


class ExportTransfer:
    """A single deadline, transfer cap, and monotonic progress across all resources."""
    def __init__(self, store, task_id, settings, check_cancelled, pieces):
        self.store, self.task_id, self.settings = store, task_id, settings
        self.check_cancelled = check_cancelled
        self.deadline = time.monotonic() + settings.download_timeout
        self.pieces = pieces
        self.done = 0
        self.received = 0
        self.progress = 5.0
        self.last_update = time.monotonic()
        self.last_bytes = 0

    def check(self):
        self.check_cancelled()
        if time.monotonic() >= self.deadline:
            raise AppError("DOWNLOAD_TIMEOUT", "资源导出超时，请重试。", 504)

    def report(self, fraction=0.0, *, force=False):
        self.progress = max(self.progress, min(90, 5 + 85 * (self.done + fraction) / self.pieces))
        current = time.monotonic()
        if force or current - self.last_update >= 0.4:
            self.store.update(self.task_id, progress=self.progress, downloaded_bytes=self.received,
                              speed_bps=(self.received - self.last_bytes) / max(0.001, current - self.last_update))
            self.last_update, self.last_bytes = current, self.received

    def download(self, urls, headers, destination, kind):
        last_error = None
        for url in urls[:3]:
            self.check()
            destination.unlink(missing_ok=True)
            response = connection = None
            try:
                response, connection = open_media(url, headers,
                    timeout=min(self.settings.network_timeout, max(0.1, self.deadline - time.monotonic())))
                if response.status != 200:
                    raise AppError("DOWNLOAD_HTTP_ERROR", f"资源服务器返回 {response.status}，请重新解析或稍后重试。", 502)
                mime = (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
                if mime and mime != "application/octet-stream" and not mime.startswith(kind + "/"):
                    raise AppError("INVALID_MEDIA", "服务器没有返回预期的媒体文件。", 422)
                length = response.getheader("Content-Length")
                total = int(length) if length and length.isdigit() else None
                if total is not None and self.received + total > self.settings.max_download_bytes:
                    raise AppError("FILE_TOO_LARGE", "所选资源合计超过单任务下载上限。", 413)
                self.store.update(self.task_id, status="downloading", total_bytes=None)
                received = 0
                with destination.open("wb") as output:
                    while True:
                        self.check()
                        chunk = response.read1(128 * 1024)
                        if not chunk:
                            break
                        received += len(chunk)
                        self.received += len(chunk)
                        if self.received > self.settings.max_download_bytes:
                            raise AppError("FILE_TOO_LARGE", "所选资源合计超过单任务下载上限。", 413)
                        output.write(chunk)
                        # Reserve a small part of this component's progress for its decode check.
                        self.report(min(0.95, received / total * 0.95) if total else 0)
                self.check()
                if not received or (total is not None and received != total):
                    raise AppError("INCOMPLETE_DOWNLOAD", "资源下载不完整，请重试。", 502)
                self.store.update(self.task_id, status="verifying", speed_bps=None)
                if kind == "image":
                    extension, _ = verify_image(destination, self.check, timeout=self.settings.verify_timeout)
                else:
                    verify_media(destination, self.check, timeout=self.settings.verify_timeout)
                    extension = ".mp4"
                self.check()
                self.done += 1
                self.report(force=True)
                return extension
            except AppError as exc:
                last_error = exc
                if exc.code in {"UNSAFE_URL", "FILE_TOO_LARGE", "DOWNLOAD_TIMEOUT", "VERIFY_TIMEOUT", "FFMPEG_UNAVAILABLE"}:
                    raise
            except (OSError, http.client.HTTPException):
                last_error = AppError("NETWORK_ERROR", "资源下载网络异常，请检查网络后重试。", 502)
            finally:
                if response:
                    response.close()
                if connection:
                    connection.close()
        raise last_error or AppError("NO_MEDIA_URL", "没有可用的资源地址。", 422)


def write_archive(destination, entries, manifest, check):
    # Media is already compressed. Streaming ZIP_STORED avoids whole-file memory copies.
    with ZipFile(destination, "w", compression=ZIP_STORED, allowZip64=True) as archive:
        for path in entries:
            check()
            with path.open("rb") as source, archive.open(path.name, "w", force_zip64=True) as output:
                while chunk := source.read(1024 * 1024):
                    check()
                    output.write(chunk)
        check()
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    check()


def export_note(task, store, settings, check_cancelled):
    from app.providers.xiaohongshu import resolve, ProviderError
    task_id = task["id"]
    temporary = settings.tmp_dir / f"{task_id}.part"
    final = None
    try:
        check_cancelled()
        try:
            note = resolve(task["source_text"])
        except ProviderError as exc:
            raise AppError(exc.code, exc.message, 422) from exc
        check_cancelled()
        selected = select_assets(note, task.get("asset_ids"))
        store.update(task_id, title=note.title, author=note.author, asset_ids=[item.id for item in selected],
                     asset_count=len(selected), finished_assets=0, format_label="图片 / 视频")
        transfer = ExportTransfer(store, task_id, settings, check_cancelled, len(selected))
        temporary.mkdir(mode=0o700)
        files = []
        manifest = {"version": 1, "platform": "xiaohongshu", "note_id": note.id,
                    "title": note.title, "author": note.author, "assets": []}
        for index, asset in enumerate(selected, 1):
            transfer.check()
            stem = f"{index:03d}_{asset.kind}"
            image = video = None
            if asset.kind == "image":
                image = temporary / (stem + "_source.part")
                extension = transfer.download(asset.image_urls, note.headers, image, "image")
                renamed = temporary / (stem + extension)
                image = image.replace(renamed)
            if asset.kind == "video":
                video = temporary / (stem + ".mp4")
                transfer.download(asset.video_urls, note.headers, video, "video")
            exported = [image if asset.kind == "image" else video]
            files.extend(exported)
            if sum(path.stat().st_size for path in files) > settings.max_download_bytes:
                raise AppError("FILE_TOO_LARGE", "导出文件合计超过单任务大小上限。", 413)
            manifest["assets"].append({"id": asset.id, "kind": asset.kind, "label": asset.label,
                "width": asset.width, "height": asset.height, "duration": asset.duration,
                "files": [path.name for path in exported], "watermark_status": asset.watermark_status})
            store.update(task_id, finished_assets=index)
        transfer.check()
        store.update(task_id, status="verifying", progress=95, speed_bps=None,
                     downloaded_bytes=transfer.received, total_bytes=transfer.received)
        if len(selected) > 1:
            output = temporary / "export.zip"
            write_archive(output, files, manifest, transfer.check)
        else:
            output = files[0]
        transfer.check()
        size = output.stat().st_size
        if size > settings.max_download_bytes:
            raise AppError("FILE_TOO_LARGE", "导出文件超过单任务大小上限。", 413)
        filename = safe_filename(task_id, note.title, output.suffix)
        final = settings.downloads_dir / filename
        output.replace(final)
        transfer.check()
        if not store.update(task_id, status="completed", progress=100, file_name=filename,
                            file_size=size, speed_bps=None, error=None):
            final.unlink(missing_ok=True)
    finally:
        if temporary.is_dir() and not temporary.is_symlink():
            shutil.rmtree(temporary)
        if final and store.get(task_id)["status"] != "completed":
            final.unlink(missing_ok=True)
