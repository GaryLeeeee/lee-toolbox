"""One durable SQLite worker. Can also be launched independently with WORKER=0 API."""
import fcntl
import logging
import os
import signal
import time
from pathlib import Path

from app.core.errors import AppError, TaskCancelled, WorkerStopping
from app.core.settings import get_settings
from app.storage.database import Store
from app.services.downloader import download_media
from app.services.files import safe_filename
from app.services.media import verify_media

log = logging.getLogger("lee_toolbox.worker")
_stopping = False


def stop(signum, frame):
    global _stopping
    _stopping = True


def execute_task(task, store, settings):
    from app.providers.douyin import resolve, ProviderError
    task_id = task["id"]
    temporary = settings.tmp_dir / f"{task_id}.part"
    final = None

    def check():
        if _stopping:
            raise WorkerStopping()
        if store.get(task_id)["status"] == "cancelled":
            raise TaskCancelled()

    try:
        check()
        media = resolve(task["source_text"])
        check()
        if task.get("format_id"):
            selected = next((item for item in media.formats if item.id == task["format_id"]), None)
            if selected is None:
                raise AppError("FORMAT_UNAVAILABLE", "所选画质已变化，请重新解析并选择画质。", 409)
        else:
            selected = media.formats[0] if media.formats else None
        if selected is None:
            raise AppError("NO_FORMATS", "该作品没有可下载的视频版本。", 422)
        store.update(task_id, title=media.title, author=media.author, format_id=selected.id, format_label=selected.label)
        size = download_media(selected, media.headers, temporary, store, task_id, settings, check)
        check()
        store.update(task_id, status="verifying", progress=95, speed_bps=None)
        verify_media(temporary, check, timeout=settings.verify_timeout)
        check()
        filename = safe_filename(task_id, media.title)
        final = settings.downloads_dir / filename
        temporary.replace(final)
        if not store.update(task_id, status="completed", progress=100, file_name=filename, file_size=size, error=None):
            final.unlink(missing_ok=True)
    except TaskCancelled:
        pass
    except WorkerStopping:
        store.update(task_id, status="interrupted", speed_bps=None,
                     error={"code": "WORKER_INTERRUPTED", "message": "服务停止导致任务中断，可重新尝试。"})
    except (AppError, ProviderError) as exc:
        store.update(task_id, status="failed", speed_bps=None, error={"code": exc.code, "message": exc.message})
        log.warning("Task %s failed: %s", task_id, exc.code)
    except Exception:
        store.update(task_id, status="failed", speed_bps=None,
                     error={"code": "TASK_FAILED", "message": "任务处理失败，请稍后重试。"})
        log.exception("Task %s failed unexpectedly", task_id)
    finally:
        temporary.unlink(missing_ok=True)
        if final and store.get(task_id)["status"] != "completed":
            final.unlink(missing_ok=True)


def recover_files(store, settings):
    """Clean only worker-owned remnants after interruption, retaining completed files."""
    store.recover()
    for stale in settings.tmp_dir.glob("*.part"):
        if stale.is_file() and not stale.is_symlink():
            stale.unlink(missing_ok=True)
    interrupted = {task["id"] for task in store.list("interrupted")}
    for candidate in settings.downloads_dir.iterdir():
        task_id = candidate.name.split("_", 1)[0]
        if task_id in interrupted and candidate.suffix == ".mp4" and candidate.is_file() and not candidate.is_symlink():
            candidate.unlink(missing_ok=True)


def run():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    settings.prepare()
    lock_path = settings.data_dir / "worker.lock"
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log.error("Another worker already owns this data directory")
            return 2
        lock.seek(0)
        lock.truncate()
        lock.write(str(os.getpid()))
        lock.flush()
        store = Store(settings.db_path)
        store.initialize()
        recover_files(store, settings)
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        log.info("Worker ready")
        while not _stopping:
            task = store.claim()
            if task:
                execute_task(task, store, settings)
            else:
                time.sleep(0.3)
        log.info("Worker stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
