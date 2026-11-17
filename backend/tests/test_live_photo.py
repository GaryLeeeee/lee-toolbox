import json
from pathlib import Path
import subprocess
import time

import pytest
from PIL import Image

from app.core.errors import AppError, TaskCancelled
from app.services import live_photo
from app.services.media import ffmpeg_binary, verify_media


def test_unavailable_platform_is_explicit(monkeypatch, tmp_path):
    monkeypatch.setattr(live_photo.platform, "system", lambda: "Linux")
    with pytest.raises(AppError, match="macOS") as error:
        live_photo.export_live_photo(tmp_path / "source.jpg", tmp_path / "source.mp4", tmp_path / "pair", lambda: None)
    assert error.value.code == "LIVE_PHOTO_UNAVAILABLE"
    assert not list(tmp_path.iterdir())


def test_cancelled_pair_removes_both_partial_outputs(monkeypatch, tmp_path):
    monkeypatch.setattr(live_photo, "is_available", lambda: True)
    monkeypatch.setattr(live_photo, "_binary", lambda *args: Path("native-helper"))

    def cancelled(*args):
        (tmp_path / "pair.jpg").write_bytes(b"partial image")
        (tmp_path / "pair.mov").write_bytes(b"partial movie")
        raise TaskCancelled()

    monkeypatch.setattr(live_photo, "_run", cancelled)
    with pytest.raises(TaskCancelled):
        live_photo.export_live_photo(tmp_path / "source.jpg", tmp_path / "source.mp4", tmp_path / "pair", lambda: None)
    assert not list(tmp_path.iterdir())


def test_existing_pair_is_never_overwritten(monkeypatch, tmp_path):
    monkeypatch.setattr(live_photo, "is_available", lambda: True)
    original = tmp_path / "pair.jpg"
    original.write_bytes(b"existing")
    with pytest.raises(AppError) as error:
        live_photo.export_live_photo(tmp_path / "source.jpg", tmp_path / "source.mp4", tmp_path / "pair", lambda: None)
    assert error.value.code == "LIVE_PHOTO_OUTPUT_EXISTS"
    assert original.read_bytes() == b"existing"


@pytest.mark.skipif(not live_photo.is_available() or not ffmpeg_binary(), reason="Requires macOS command line tools and FFmpeg")
def test_pair_is_recognized_by_apple_and_preserves_motion(tmp_path, monkeypatch):
    monkeypatch.setenv("LEE_TOOLBOX_DATA_DIR", str(tmp_path / "data"))
    image = tmp_path / "source.jpg"
    video = tmp_path / "source.mp4"
    Image.new("RGB", (240, 320), "navy").save(image)
    subprocess.run([ffmpeg_binary(), "-hide_banner", "-loglevel", "error", "-nostdin",
                    "-f", "lavfi", "-i", "color=c=navy:s=240x320:r=30:d=1.2",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=1.2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(video)], check=True)
    originals = (image.read_bytes(), video.read_bytes())
    photo, movie = live_photo.export_live_photo(image, video, tmp_path / "paired", lambda: None)
    binary = live_photo._binary(lambda: None, time.monotonic() + 30)
    result = subprocess.run([str(binary), "validate", str(photo), str(movie)], capture_output=True, check=True, timeout=30)
    metadata = json.loads(result.stdout)
    assert len(metadata["identifier"]) == 36
    assert 0 < metadata["still_image_time"] < metadata["duration"]
    assert metadata["duration"] == pytest.approx(1.2, abs=0.1)
    with Image.open(photo) as decoded:
        assert decoded.size == (240, 320)
    verify_media(movie, lambda: None, timeout=30)
    assert (image.read_bytes(), video.read_bytes()) == originals
