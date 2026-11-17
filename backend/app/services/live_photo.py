"""Generate Apple Live Photo resources using the local macOS media frameworks."""
import hashlib
import os
import platform
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from app.core.errors import AppError
from app.core.settings import get_settings

SOURCE = Path(__file__).resolve().parents[1] / "native" / "live_photo.swift"


def is_available() -> bool:
    return platform.system() == "Darwin" and bool(shutil.which("swiftc")) and SOURCE.is_file()


def _run(command: list[str], check_cancelled, deadline: float):
    # Compiler/framework diagnostics may contain local paths; never expose them
    # through task errors. Temporary logs also avoid an undrained PIPE deadlock.
    with tempfile.TemporaryFile() as diagnostics:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=diagnostics, stderr=diagnostics,
                                   start_new_session=True)
        try:
            while process.poll() is None:
                check_cancelled()
                if time.monotonic() >= deadline:
                    raise AppError("LIVE_PHOTO_TIMEOUT", "Live Photo 配对处理超时，请重试。", 504)
                time.sleep(0.1)
            check_cancelled()
            if process.returncode:
                raise AppError("LIVE_PHOTO_FAILED", "Live Photo 配对或 Apple 格式校验失败，未生成不完整配对。", 422)
        finally:
            if process.poll() is None:
                # swiftc may have a compiler child. Stop the whole owned group
                # before removing partial files so no child writes them again.
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()


def _binary(check_cancelled, deadline: float) -> Path:
    import fcntl

    digest = hashlib.sha256(SOURCE.read_bytes() + platform.machine().encode()).hexdigest()[:20]
    cache = get_settings().data_dir / "cache" / "live-photo"
    cache.mkdir(parents=True, exist_ok=True)
    binary = cache / digest
    with (cache / "compile.lock").open("a") as lock:
        while True:
            check_cancelled()
            if time.monotonic() >= deadline:
                raise AppError("LIVE_PHOTO_TIMEOUT", "Live Photo 组件初始化超时，请重试。", 504)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(0.1)
        if not binary.is_file():
            temporary = cache / f"{digest}.{os.getpid()}.part"
            try:
                _run([shutil.which("swiftc"), "-swift-version", "5", "-O", str(SOURCE), "-o", str(temporary)],
                     check_cancelled, deadline)
                temporary.replace(binary)
            finally:
                temporary.unlink(missing_ok=True)
    return binary


def export_live_photo(image_path: Path, video_path: Path, output_stem: Path,
                      check_cancelled, timeout: int = 120) -> tuple[Path, Path]:
    """Return a matching JPEG/MOV pair, verified by Apple's PHLivePhoto reader.

    The caller must first validate the downloaded still and video. No user photo
    library is opened or modified. Cancellation removes both partial outputs.
    """
    check_cancelled()
    if not is_available():
        raise AppError("LIVE_PHOTO_UNAVAILABLE", "Live Photo 配对需在 macOS 上安装 Xcode 命令行工具；当前仍可导出普通图片和视频。", 503)
    photo = Path(str(output_stem) + ".jpg")
    movie = Path(str(output_stem) + ".mov")
    if photo.exists() or movie.exists():
        raise AppError("LIVE_PHOTO_OUTPUT_EXISTS", "Live Photo 输出文件已存在，请重新创建任务。", 409)
    deadline = time.monotonic() + timeout
    try:
        binary = _binary(check_cancelled, deadline)
        _run([str(binary), "pair", str(image_path), str(video_path), str(output_stem)], check_cancelled, deadline)
        if not photo.is_file() or not movie.is_file() or not photo.stat().st_size or not movie.stat().st_size:
            raise AppError("LIVE_PHOTO_FAILED", "Live Photo 配对文件不完整。", 422)
        return photo, movie
    except BaseException:
        photo.unlink(missing_ok=True)
        movie.unlink(missing_ok=True)
        raise
