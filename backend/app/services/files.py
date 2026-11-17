from pathlib import Path
import re

from app.core.errors import AppError


FILE_TYPES = {".mp4": "video/mp4", ".mov": "video/quicktime", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif",
              ".heic": "image/heic", ".heif": "image/heif", ".zip": "application/zip"}


def safe_filename(task_id: str, title: str, extension: str = ".mp4") -> str:
    if extension not in FILE_TYPES:
        raise ValueError("Unsupported file extension")
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", title).strip(" .")
    cleaned = cleaned.encode("utf-8")[:180].decode("utf-8", errors="ignore").rstrip(" .")
    return f"{task_id}_{cleaned or '媒体'}{extension}"


def task_file(task: dict, downloads_dir: Path) -> Path | None:
    name = task.get("file_name")
    if task.get("status") != "completed" or not name or name != Path(name).name or "\\" in name:
        return None
    candidate = downloads_dir / name
    if candidate.is_symlink():
        return None
    try:
        candidate.resolve().relative_to(downloads_dir.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def public_task(task: dict, downloads_dir: Path):
    return {**task, "file_available": task_file(task, downloads_dir) is not None}


def require_task_file(task, downloads_dir):
    if task["status"] != "completed":
        raise AppError("FILE_NOT_READY", "任务尚未完成，暂时没有可下载文件。", 409)
    path = task_file(task, downloads_dir)
    if path is None:
        raise AppError("FILE_NOT_FOUND", "导出文件已移动或删除。", 404)
    return path
