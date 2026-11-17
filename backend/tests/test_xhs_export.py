from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import subprocess
from zipfile import ZipFile

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.core.errors import AppError
from app.core.settings import Settings
from app.jobs import worker
from app.main import app
from app.providers import xiaohongshu as provider
from app.services import previews, xhs_export
from app.services.images import verify_image
from app.services.media import ffmpeg_binary
from app.storage.database import Store


def image_bytes(color="red", format="JPEG"):
    buffer = BytesIO()
    Image.new("RGB", (24, 32), color).save(buffer, format=format)
    return buffer.getvalue()


def asset(asset_id="image-1", kind="image", available=True, watermark_status="none"):
    return provider.XhsAsset(asset_id, kind, "测试资源", 24, 32, None,
        [f"https://sns-img-bd.xhscdn.com/{asset_id}"] if kind in {"image", "live"} else [],
        [f"https://sns-video-bd.xhscdn.com/{asset_id}"] if kind in {"video", "live"} else [],
        available=available, watermark_status=watermark_status)


def note(assets):
    return provider.ResolvedNote("xiaohongshu", "a" * 24, "../九月底?", "作者",
        "https://www.xiaohongshu.com/explore/" + "a" * 24, assets, [], {"Referer": "https://www.xiaohongshu.com/"})


class Response:
    def __init__(self, data, mime="image/jpeg", *, length=None, status=200):
        self.data = BytesIO(data)
        self.mime = mime
        self.length = str(len(data)) if length is None else length
        self.status = status
        self.closed = False

    def getheader(self, key):
        return {"Content-Type": self.mime, "Content-Length": self.length}.get(key)

    def read1(self, count):
        return self.data.read(count)

    def close(self):
        self.closed = True


class Connection:
    def close(self):
        pass


@pytest.fixture
def work(tmp_path, monkeypatch):
    settings = Settings(tmp_path, tmp_path / "frontend", False)
    settings.prepare()
    store = Store(settings.db_path)
    store.initialize()
    media = note([asset()])
    monkeypatch.setattr(worker, "_stopping", False)
    monkeypatch.setattr(provider, "resolve", lambda _: media)
    monkeypatch.setattr(xhs_export, "open_media", lambda *args, **kwargs: (Response(image_bytes()), Connection()))
    return settings, store, media


def execute(work, selection=None):
    settings, store, _ = work
    task = store.create("share", tool_id="xiaohongshu-export", asset_ids=selection)
    claimed = store.claim()
    worker.execute_task(claimed, store, settings)
    return store.get(task["id"])


def test_single_image_keeps_original_bytes_and_detects_extension(work):
    settings, _, _ = work
    task = execute(work)
    assert task["status"] == "completed"
    assert task["asset_ids"] == ["image-1"]
    assert task["asset_count"] == task["finished_assets"] == 1
    assert task["file_name"].endswith(".jpg")
    assert (settings.downloads_dir / task["file_name"]).read_bytes() == image_bytes()
    assert list(settings.tmp_dir.iterdir()) == []


def test_only_selected_assets_are_exported_in_order_with_manifest(work, monkeypatch):
    settings, _, media = work
    media.assets = [asset("one"), asset("two"), asset("three")]
    requested = []
    def open_media(url, *args, **kwargs):
        requested.append(url.rsplit("/", 1)[-1])
        return Response(image_bytes("blue" if requested[-1] == "two" else "red")), Connection()
    monkeypatch.setattr(xhs_export, "open_media", open_media)
    task = execute(work, ["two", "one"])
    assert task["status"] == "completed"
    assert requested == ["two", "one"]
    with ZipFile(settings.downloads_dir / task["file_name"]) as archive:
        assert set(archive.namelist()) == {"001_image.jpg", "002_image.jpg", "manifest.json"}
        manifest = json.loads(archive.read("manifest.json"))
        assert [item["id"] for item in manifest["assets"]] == ["two", "one"]
        assert archive.read("001_image.jpg") == image_bytes("blue")
        assert b"xhscdn" not in archive.read("manifest.json")


@pytest.fixture
def video_data(tmp_path):
    binary = ffmpeg_binary()
    if not binary:
        pytest.skip("FFmpeg unavailable")
    sample = tmp_path / "sample.mp4"
    subprocess.run([binary, "-hide_banner", "-v", "error", "-f", "lavfi", "-i", "color=size=32x32:rate=5",
                    "-t", "0.4", "-pix_fmt", "yuv420p", "-y", str(sample)], check=True, timeout=15)
    return sample.read_bytes()


def test_live_components_export_independent_jpeg_mp4_with_watermark_manifest(work, monkeypatch, video_data):
    settings, _, media = work
    media.assets = [asset("still-1"), asset("motion-1", "video", watermark_status="present")]
    monkeypatch.setattr(xhs_export, "open_media", lambda url, *a, **kw:
        (Response(video_data, "video/mp4") if "sns-video" in url else Response(image_bytes()), Connection()))
    task = execute(work)
    assert task["status"] == "completed"
    assert task["asset_count"] == task["finished_assets"] == 2
    with ZipFile(settings.downloads_dir / task["file_name"]) as archive:
        assert set(archive.namelist()) == {"001_image.jpg", "002_video.mp4", "manifest.json"}
        still, video = json.loads(archive.read("manifest.json"))["assets"]
        assert still["kind"] == "image" and still["watermark_status"] == "none"
        assert video["kind"] == "video" and video["watermark_status"] == "present"
        assert "pair_format" not in still and "pair_format" not in video
        assert archive.read("002_video.mp4") == video_data
    assert list(settings.tmp_dir.iterdir()) == []


def test_legacy_live_pair_kind_fails_before_any_download(work, monkeypatch):
    settings, _, media = work
    media.assets = [asset("live-1", "live")]
    def unexpected(*args, **kwargs):
        pytest.fail("Unsupported Live Photo environment must not download originals")
    monkeypatch.setattr(xhs_export, "open_media", unexpected)
    result = execute(work)
    assert result["status"] == "failed" and result["error"]["code"] == "UNSUPPORTED_MEDIA"
    assert "暂不支持直接导出 Live Photo" in result["error"]["message"]
    assert list(settings.tmp_dir.iterdir()) == list(settings.downloads_dir.iterdir()) == []


@pytest.mark.parametrize("watermark_status", ["none", "present", "unknown"])
def test_single_video_passes_real_decode_validation_and_exports_mp4(work, monkeypatch, video_data, watermark_status):
    settings, _, media = work
    media.assets = [asset("video", "video", watermark_status=watermark_status)]
    monkeypatch.setattr(xhs_export, "open_media", lambda *a, **kw: (Response(video_data, "video/mp4"), Connection()))
    result = execute(work)
    assert result["status"] == "completed" and result["file_name"].endswith(".mp4")
    assert (settings.downloads_dir / result["file_name"]).read_bytes() == video_data


@pytest.mark.parametrize("selection, expected", [(["missing"], "ASSET_UNAVAILABLE"), (["unavailable"], "ASSET_UNAVAILABLE"),
                                                  (["video"], "VIDEO_UNAVAILABLE")])
def test_missing_or_unavailable_selection_fails_before_download(work, monkeypatch, selection, expected):
    _, _, media = work
    video = asset("video", "video")
    video.video_urls = []
    media.assets = [asset(), asset("unavailable", available=False), video]
    def unexpected(*args, **kwargs):
        pytest.fail("No partial export may start for an invalid selection")
    monkeypatch.setattr(xhs_export, "open_media", unexpected)
    result = execute(work, selection)
    assert result["status"] == "failed" and result["error"]["code"] == expected


def test_default_selection_excludes_unavailable_but_preserves_static_alternative(work):
    _, _, media = work
    media.assets = [asset("motion", "video", False), asset("still")]
    result = execute(work)
    assert result["status"] == "completed" and result["asset_ids"] == ["still"]


def test_any_selected_item_failure_cleans_previous_success_and_no_false_completion(work, monkeypatch):
    settings, _, media = work
    media.assets = [asset("one"), asset("two")]
    monkeypatch.setattr(xhs_export, "open_media", lambda url, *a, **kw:
        (Response(image_bytes() if url.endswith("one") else b"not-image"), Connection()))
    result = execute(work)
    assert result["status"] == "failed" and result["error"]["code"] == "INVALID_MEDIA"
    assert result["finished_assets"] == 1
    assert list(settings.tmp_dir.iterdir()) == list(settings.downloads_dir.iterdir()) == []


def test_invalid_primary_image_uses_verified_backup(work, monkeypatch):
    _, _, media = work
    media.assets[0].image_urls.append("https://sns-img-qc.xhscdn.com/backup")
    monkeypatch.setattr(xhs_export, "open_media", lambda url, *a, **kw:
        (Response(image_bytes() if url.endswith("backup") else b"bad"), Connection()))
    assert execute(work)["status"] == "completed"


def test_total_download_limit_is_shared_by_all_assets(work):
    settings, store, media = work
    media.assets = [asset("one"), asset("two")]
    bounded = replace(settings, max_download_bytes=len(image_bytes()) + 20)
    result = execute((bounded, store, media))
    assert result["status"] == "failed" and result["error"]["code"] == "FILE_TOO_LARGE"
    assert list(settings.tmp_dir.iterdir()) == list(settings.downloads_dir.iterdir()) == []


def test_progress_never_moves_back_between_resources_or_backup_urls(work, monkeypatch):
    _, store, media = work
    media.assets = [asset("one"), asset("two")]
    media.assets[0].image_urls.append("https://sns-img-qc.xhscdn.com/backup")
    progress = []
    original = store.update
    def recording(task_id, **fields):
        if "progress" in fields:
            progress.append(fields["progress"])
        return original(task_id, **fields)
    monkeypatch.setattr(store, "update", recording)
    monkeypatch.setattr(xhs_export, "open_media", lambda url, *a, **kw:
        (Response(b"bad" if url.endswith("one") else image_bytes()), Connection()))
    assert execute(work)["status"] == "completed"
    assert progress == sorted(progress) and progress[-1] == 100


def test_cancel_during_image_decode_cleans_partial_directory(work, monkeypatch):
    settings, store, _ = work
    original = xhs_export.verify_image
    def cancel_after_decode(path, check, **kwargs):
        result = original(path, check, **kwargs)
        store.cancel(store.list()[0]["id"])
        return result
    monkeypatch.setattr(xhs_export, "verify_image", cancel_after_decode)
    result = execute(work)
    assert result["status"] == "cancelled"
    assert list(settings.tmp_dir.iterdir()) == list(settings.downloads_dir.iterdir()) == []


def test_cancel_after_rename_cleans_new_final_file(work, monkeypatch):
    settings, store, _ = work
    original = store.update
    def racing_update(task_id, **fields):
        if fields.get("status") == "completed":
            store.cancel(task_id)
        return original(task_id, **fields)
    monkeypatch.setattr(store, "update", racing_update)
    result = execute(work)
    assert result["status"] == "cancelled"
    assert list(settings.tmp_dir.iterdir()) == list(settings.downloads_dir.iterdir()) == []


def test_packaging_error_removes_incomplete_zip(work, monkeypatch):
    settings, _, media = work
    media.assets = [asset("one"), asset("two")]
    def broken_archive(path, *args):
        path.write_bytes(b"partial archive")
        raise OSError("disk full")
    monkeypatch.setattr(xhs_export, "write_archive", broken_archive)
    result = execute(work)
    assert result["status"] == "failed"
    assert list(settings.tmp_dir.iterdir()) == list(settings.downloads_dir.iterdir()) == []


def test_recovery_cleans_xhs_directories_and_orphan_zip_but_keeps_completed(work):
    settings, store, _ = work
    running = store.create("share", tool_id="xiaohongshu-export")
    store.claim()
    partial = settings.tmp_dir / (running["id"] + ".part")
    partial.mkdir()
    (partial / "export.zip").write_bytes(b"unfinished")
    orphan = settings.downloads_dir / (running["id"] + "_orphan.zip")
    orphan.write_bytes(b"unfinished")
    success = store.create("complete", tool_id="xiaohongshu-export")
    success_file = settings.downloads_dir / (success["id"] + "_done.jpg")
    success_file.write_bytes(image_bytes())
    store.update(success["id"], allowed=("queued",), status="completed", file_name=success_file.name)
    worker.recover_files(store, settings)
    assert store.get(running["id"])["status"] == "interrupted"
    assert not partial.exists() and not orphan.exists() and success_file.exists()


def test_retry_keeps_tool_and_selection_without_copying_progress(work):
    _, store, media = work
    media.assets = [asset("one"), asset("two")]
    task = store.create("share", tool_id="xiaohongshu-export", asset_ids=["two"])
    store.cancel(task["id"])
    retried = store.retry(task["id"])
    assert retried["tool_id"] == "xiaohongshu-export" and retried["asset_ids"] == ["two"]
    assert retried["finished_assets"] == 0 and retried["progress"] == 0


def test_legacy_database_migration_preserves_completed_task_and_is_idempotent(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE tasks (id TEXT PRIMARY KEY, tool_id TEXT NOT NULL DEFAULT 'video-download',
            status TEXT NOT NULL,title TEXT NOT NULL,author TEXT NOT NULL DEFAULT '',source_text TEXT NOT NULL,
            format_id TEXT,format_label TEXT NOT NULL DEFAULT '自动选择',progress REAL NOT NULL DEFAULT 0,
            downloaded_bytes INTEGER NOT NULL DEFAULT 0,total_bytes INTEGER,speed_bps REAL,file_name TEXT,
            file_size INTEGER,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""")
        db.execute("""INSERT INTO tasks(id,status,title,source_text,file_name,created_at,updated_at)
            VALUES ('old','completed','保留标题','source','old.mp4','2026-01-01','2026-01-01')""")
    store = Store(path)
    store.initialize()
    store.initialize()
    old = store.get("old")
    assert old["status"] == "completed" and old["file_name"] == "old.mp4"
    assert old["title"] == "保留标题" and old["tool_id"] == "video-download"
    assert old["asset_ids"] is None and old["finished_assets"] == 0


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LEE_TOOLBOX_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LEE_TOOLBOX_WORKER", "0")
    with TestClient(app, base_url="http://127.0.0.1:8000") as value:
        yield value


@pytest.mark.parametrize("body", [
    {"tool_id": "bad"}, {"tool_id": "xiaohongshu-export", "asset_ids": []},
    {"tool_id": "xiaohongshu-export", "asset_ids": ["one", "one"]},
    {"tool_id": "xiaohongshu-export", "asset_ids": [" "]},
    {"tool_id": "xiaohongshu-export", "asset_ids": ["x" * 161]},
    {"tool_id": "xiaohongshu-export", "asset_ids": [str(n) for n in range(101)]},
    {"tool_id": "xiaohongshu-export", "format_id": "douyin-quality"},
    {"tool_id": "video-download", "asset_ids": ["one"]},
])
def test_api_rejects_invalid_tool_selection(client, body):
    response = client.post("/api/tasks", json={"source_text": "share", **body})
    assert response.status_code == 422 and response.json()["error"]["code"] == "INVALID_INPUT"


def test_xhs_api_preview_tokens_hide_signed_media_urls_and_expire(client, monkeypatch):
    media = note([asset()])
    media.assets[0].image_urls = ["https://sns-img-bd.xhscdn.com/private-signature"]
    media.headers["Cookie"] = "private-cookie"
    monkeypatch.setattr(provider, "resolve", lambda _: media)
    monkeypatch.setattr(previews, "open_media", lambda *a, **kw: (Response(image_bytes()), Connection()))
    response = client.post("/api/xhs/resolve", json={"text": "share"})
    assert response.status_code == 200 and "private" not in response.text
    preview = response.json()["assets"][0]["preview_url"]
    assert preview.startswith("/api/xhs/previews/")
    loaded = client.get(preview)
    assert loaded.status_code == 200 and loaded.headers["content-type"] == "image/jpeg"
    assert loaded.content == image_bytes() and loaded.headers["cache-control"] == "no-store"
    app.state.previews._entries.clear()
    assert client.get(preview).status_code == 404
    assert client.get("/api/xhs/previews/https://evil.example/image").status_code == 404


def test_preview_registry_has_capacity_and_ttl(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(previews.time, "monotonic", lambda: clock[0])
    registry = previews.PreviewRegistry(capacity=2, ttl=10)
    first = registry.register(["one"], {}).rsplit("/", 1)[-1]
    second = registry.register(["two"], {}).rsplit("/", 1)[-1]
    registry.register(["three"], {})
    with pytest.raises(AppError, match="预览已过期"):
        registry.get(first)
    assert registry.get(second).urls == ("two",)
    clock[0] = 110.0
    with pytest.raises(AppError, match="预览已过期"):
        registry.get(second)


@pytest.mark.parametrize("response, code", [
    (Response(b"<svg/>", "image/svg+xml"), "INVALID_MEDIA"),
    (Response(image_bytes(), "text/html"), "INVALID_MEDIA"),
    (Response(b"fake image", "image/jpeg"), "INVALID_MEDIA"),
    (Response(image_bytes(), "image/png"), "INVALID_MEDIA"),
    (Response(b"x", "image/jpeg", length=str(previews.MAX_PREVIEW_BYTES + 1)), "PREVIEW_TOO_LARGE"),
])
def test_previews_reject_bad_type_content_or_size(monkeypatch, response, code):
    monkeypatch.setattr(previews, "open_media", lambda *a, **kw: (response, Connection()))
    with pytest.raises(AppError) as error:
        previews.fetch_preview(previews.Preview(("https://sns-img-bd.xhscdn.com/img",), {}, 99999999))
    assert error.value.code == code
    assert response.closed


def test_preview_stream_limit_without_content_length(monkeypatch):
    response = Response(b"x" * (previews.MAX_PREVIEW_BYTES + 1), "image/jpeg", length="")
    monkeypatch.setattr(previews, "open_media", lambda *a, **kw: (response, Connection()))
    with pytest.raises(AppError) as error:
        previews.fetch_preview(previews.Preview(("https://sns-img-bd.xhscdn.com/img",), {}, 99999999))
    assert error.value.code == "PREVIEW_TOO_LARGE" and response.closed


@pytest.mark.parametrize("extension, mime", [(".jpg", "image/jpeg"), (".png", "image/png"),
    (".webp", "image/webp"), (".mp4", "video/mp4"), (".zip", "application/zip")])
def test_download_endpoint_uses_actual_export_type(client, extension, mime):
    response = client.post("/api/tasks", json={"tool_id": "xiaohongshu-export", "source_text": "share", "asset_ids": ["one"]})
    assert response.status_code == 201
    task_id = response.json()["id"]
    filename = task_id + "_export" + extension
    (app.state.settings.downloads_dir / filename).write_bytes(b"export")
    app.state.store.update(task_id, allowed=("queued",), status="completed", file_name=filename)
    result = client.get(f"/api/tasks/{task_id}/file")
    assert result.headers["content-type"] == mime
    assert "export" + extension in result.headers["content-disposition"]
    assert task_id not in result.headers["content-disposition"]


def test_image_validation_rejects_truncation_and_preserves_supported_formats():
    for format, extension in [("JPEG", ".jpg"), ("PNG", ".png"), ("WEBP", ".webp")]:
        data = image_bytes(format=format)
        assert verify_image(data)[0] == extension
        with pytest.raises(AppError) as error:
            verify_image(data[:len(data) // 2])
        assert error.value.code == "INVALID_MEDIA"
