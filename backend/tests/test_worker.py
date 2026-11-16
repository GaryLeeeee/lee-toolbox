from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from app.core.errors import AppError
from app.core.settings import Settings
from app.jobs import worker
from app.providers import douyin
from app.services.files import safe_filename
from app.services.media import ffmpeg_binary, verify_media
from app.storage.database import Store


@pytest.fixture
def work(tmp_path, monkeypatch):
    settings = Settings(tmp_path, tmp_path / "frontend", False)
    settings.prepare()
    store = Store(settings.db_path)
    store.initialize()
    task = store.create("source", "format")
    store.claim()
    monkeypatch.setattr(worker, "_stopping", False)
    media = douyin.ResolvedMedia("douyin", "1", "中文标题", "作者", None, 5, "url", [
        douyin.MediaFormat("format", "720p", 720, 1280, "h264", 100, 5, ["url"])
    ], {})
    monkeypatch.setattr(douyin, "resolve", lambda _: media)
    return settings, store, task, media


def fake_download(media_format, headers, destination, store, task_id, settings, check):
    destination.write_bytes(b"video")
    return 5


def test_worker_creates_completed_file(work, monkeypatch):
    settings, store, task, _ = work
    monkeypatch.setattr(worker, "download_media", fake_download)
    monkeypatch.setattr(worker, "verify_media", lambda *args, **kwargs: None)
    worker.execute_task(task, store, settings)
    done = store.get(task["id"])
    assert done["status"] == "completed" and done["file_size"] == 5
    assert (settings.downloads_dir / done["file_name"]).read_bytes() == b"video"
    assert list(settings.tmp_dir.iterdir()) == []


def test_cancellation_during_verification_cleans_output(work, monkeypatch):
    settings, store, task, _ = work
    monkeypatch.setattr(worker, "download_media", fake_download)
    monkeypatch.setattr(worker, "verify_media", lambda *args, **kwargs: store.cancel(task["id"]))
    worker.execute_task(task, store, settings)
    assert store.get(task["id"])["status"] == "cancelled"
    assert list(settings.tmp_dir.iterdir()) == []
    assert list(settings.downloads_dir.iterdir()) == []


def test_cancel_race_after_file_move_does_not_publish_file(work, monkeypatch):
    settings, store, task, _ = work
    monkeypatch.setattr(worker, "download_media", fake_download)
    monkeypatch.setattr(worker, "verify_media", lambda *args, **kwargs: None)
    original_update = store.update
    def racing_update(task_id, **kwargs):
        if kwargs.get("status") == "completed":
            store.cancel(task_id)
        return original_update(task_id, **kwargs)
    monkeypatch.setattr(store, "update", racing_update)
    worker.execute_task(task, store, settings)
    assert store.get(task["id"])["status"] == "cancelled"
    assert list(settings.downloads_dir.iterdir()) == []


def test_missing_selected_format_fails_without_silent_downgrade(work, monkeypatch):
    settings, store, task, media = work
    media.formats[0].id = "changed-format"
    with patch.object(worker, "download_media") as download:
        worker.execute_task(task, store, settings)
    download.assert_not_called()
    assert store.get(task["id"])["error"]["code"] == "FORMAT_UNAVAILABLE"


def test_long_unicode_title_stays_within_filesystem_limits():
    filename = safe_filename("a" * 36, "中文🚀" * 100)
    assert len(filename.encode("utf-8")) <= 255
    assert filename.endswith(".mp4")
    assert "/" not in safe_filename("id", "../../bad/name")


def test_ffmpeg_accepts_real_mp4_and_rejects_text(tmp_path):
    binary = ffmpeg_binary()
    if binary is None:
        pytest.skip("FFmpeg not installed")
    path = tmp_path / "sample.mp4"
    subprocess.run([binary, "-hide_banner", "-v", "error", "-f", "lavfi", "-i", "color=size=32x32:rate=5",
                    "-t", "0.4", "-pix_fmt", "yuv420p", "-y", str(path)], check=True, timeout=15)
    verify_media(path, lambda: None, timeout=15)
    path.write_text("not a video")
    with pytest.raises(AppError) as error:
        verify_media(path, lambda: None, timeout=15)
    assert error.value.code == "INVALID_MEDIA"


def test_recovery_removes_interrupted_files_but_preserves_completed(work):
    settings, store, task, _ = work
    orphan = settings.downloads_dir / f'{task["id"]}_orphan.mp4'
    orphan.write_bytes(b"orphan")
    (settings.tmp_dir / f'{task["id"]}.part').write_bytes(b"partial")
    complete = store.create("complete")
    store.update(complete["id"], allowed=("queued",), status="completed", file_name=f'{complete["id"]}_complete.mp4')
    finished = settings.downloads_dir / f'{complete["id"]}_complete.mp4'
    finished.write_bytes(b"completed")
    worker.recover_files(store, settings)
    assert store.get(task["id"])["status"] == "interrupted"
    assert not orphan.exists() and finished.exists()
    assert list(settings.tmp_dir.iterdir()) == []


def test_worker_stop_preserves_retryable_interrupted_state(work, monkeypatch):
    settings, store, task, _ = work
    monkeypatch.setattr(worker, "_stopping", True)
    worker.execute_task(task, store, settings)
    assert store.get(task["id"])["status"] == "interrupted"
    assert store.retry(task["id"])["status"] == "queued"


def test_worker_lock_prevents_second_worker_recovery(tmp_path):
    import os
    import sys
    import time
    settings = Settings(tmp_path, tmp_path / "frontend", False)
    settings.prepare()
    store = Store(settings.db_path)
    store.initialize()
    running = store.create("source")
    store.update(running["id"], allowed=("queued",), status="downloading")
    environment = {**os.environ, "LEE_TOOLBOX_DATA_DIR": str(tmp_path)}
    first = subprocess.Popen([sys.executable, "-m", "app.jobs.worker"], env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 5
        while store.get(running["id"])["status"] != "interrupted" and time.monotonic() < deadline:
            time.sleep(0.05)
        assert (tmp_path / "worker.lock").exists()
        assert store.get(running["id"])["status"] == "interrupted"
        store.update(running["id"], allowed=("interrupted",), status="downloading")
        second = subprocess.run([sys.executable, "-m", "app.jobs.worker"], env=environment, capture_output=True, timeout=5)
        assert second.returncode == 2
        assert store.get(running["id"])["status"] == "downloading"
    finally:
        first.terminate()
        first.wait(timeout=5)
        if first.stderr:
            first.stderr.close()
