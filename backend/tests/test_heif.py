from io import BytesIO

from PIL import Image
import pytest

from app.core.errors import AppError, TaskCancelled
from app.core.settings import Settings
from app.jobs import worker
from app.providers import xiaohongshu as provider
from app.services import images, previews, xhs_export
from app.services.files import FILE_TYPES
from app.storage.database import Store


def heic_bytes(*, orientation=None, size=(64, 32), frames=1):
    image = Image.new("RGB", size, "red")
    output = BytesIO()
    exif = Image.Exif()
    if orientation:
        exif[274] = orientation
    image.save(output, format="HEIF", exif=exif.tobytes(), quality=90,
               save_all=frames > 1,
               append_images=[Image.new("RGB", size, "blue") for _ in range(frames - 1)])
    return output.getvalue()


@pytest.fixture(scope="module")
def heic():
    return heic_bytes()


class Response:
    status = 200

    def __init__(self, data, mime):
        self.data, self.mime = BytesIO(data), mime
        self.size = len(data)

    def getheader(self, key):
        return {"Content-Type": self.mime, "Content-Length": str(self.size)}.get(key)

    def read1(self, count):
        return self.data.read(count)

    def close(self):
        self.data.close()


class Connection:
    def close(self):
        pass


def test_heic_verification_accepts_bytes_and_file_without_changing_original(heic, tmp_path):
    path = tmp_path / "source.part"
    path.write_bytes(heic)
    assert images.verify_image(heic) == (".heic", "image/heic")
    assert images.verify_image(path) == (".heic", "image/heic")
    assert path.read_bytes() == heic


@pytest.mark.parametrize("mime", sorted(images.HEIF_MIMES))
def test_heif_mime_aliases_preview_as_browser_jpeg(heic, monkeypatch, mime):
    monkeypatch.setattr(previews, "open_media", lambda *a, **kw: (Response(heic, mime), Connection()))
    data, result_mime = previews.fetch_preview(previews.Preview(("https://sns-img-bd.xhscdn.com/source",), {}, 100))
    assert result_mime == "image/jpeg" and data != heic
    with Image.open(BytesIO(data)) as image:
        assert image.format == "JPEG" and image.size == (64, 32)
        image.load()


def test_heic_preview_respects_container_orientation_without_double_rotation():
    data = heic_bytes(orientation=6)
    assert images.verify_image(data)[1] == "image/heic"
    preview, mime = images.browser_preview(data, "image/heic")
    with Image.open(BytesIO(preview)) as image:
        assert image.size == (32, 64)
        assert image.getexif().get(274, 1) == 1


def test_heic_preview_is_bounded_and_original_stays_full_size():
    data = heic_bytes(size=(1700, 850))
    preview, mime = images.browser_preview(data, "image/heic")
    with Image.open(BytesIO(preview)) as image:
        assert image.size == (1600, 800)
    with Image.open(BytesIO(data)) as original:
        assert original.size == (1700, 850)


def test_heic_malformed_content_and_mime_mismatch_are_rejected(heic, monkeypatch):
    with pytest.raises(AppError) as error:
        images.verify_image(heic[:100])
    assert error.value.code == "INVALID_MEDIA"
    monkeypatch.setattr(previews, "open_media", lambda *a, **kw: (Response(heic, "image/png"), Connection()))
    with pytest.raises(AppError) as error:
        previews.fetch_preview(previews.Preview(("https://sns-img-bd.xhscdn.com/source",), {}, 100))
    assert error.value.code == "INVALID_MEDIA"


def test_heic_verification_keeps_pixel_cancellation_and_timeout_guards(heic, monkeypatch):
    monkeypatch.setattr(images, "MAX_PIXELS", 100)
    with pytest.raises(AppError, match="安全解码范围"):
        images.verify_image(heic)
    def cancelled():
        raise TaskCancelled()
    with pytest.raises(TaskCancelled):
        images.verify_image(heic, check_cancelled=cancelled)
    with pytest.raises(AppError) as error:
        images.browser_preview(heic, "image/heic", timeout=0)
    assert error.value.code == "PREVIEW_TIMEOUT"


def test_heic_multiframe_total_pixel_limit_is_enforced(monkeypatch):
    data = heic_bytes(frames=2)
    monkeypatch.setattr(images, "MAX_FRAME_PIXELS", 3000)
    with pytest.raises(AppError, match="安全解码范围"):
        images.verify_image(data)


def test_export_keeps_original_heic_bytes_and_download_type(heic, monkeypatch, tmp_path):
    settings = Settings(tmp_path, tmp_path / "frontend", False)
    settings.prepare()
    store = Store(settings.db_path)
    store.initialize()
    asset = provider.XhsAsset("image-1", "image", "原图", 64, 32, None,
                              ["https://sns-img-bd.xhscdn.com/source"], [], watermark_status="none")
    note = provider.ResolvedNote("xiaohongshu", "a" * 24, "HEIC 笔记", "作者",
                                 "https://www.xiaohongshu.com/explore/" + "a" * 24, [asset], [], {})
    monkeypatch.setattr(provider, "resolve", lambda _: note)
    monkeypatch.setattr(worker, "_stopping", False)
    monkeypatch.setattr(xhs_export, "open_media", lambda *a, **kw: (Response(heic, "image/heic"), Connection()))
    task = store.create("share", tool_id="xiaohongshu-export", asset_ids=[asset.id])
    worker.execute_task(store.claim(), store, settings)
    result = store.get(task["id"])
    assert result["status"] == "completed", result["error"]
    target = settings.downloads_dir / result["file_name"]
    assert target.suffix == ".heic" and target.read_bytes() == heic
    assert FILE_TYPES[target.suffix] == "image/heic"
    assert list(settings.tmp_dir.iterdir()) == []
