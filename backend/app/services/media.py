from functools import lru_cache
import shutil
import subprocess
import time
from pathlib import Path

from app.core.errors import AppError


@lru_cache(maxsize=1)
def ffmpeg_binary() -> str | None:
    binary = shutil.which("ffmpeg")
    if binary:
        return binary
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError, OSError):
        return None


def verify_media(path: Path, check_cancelled, timeout=300):
    binary = ffmpeg_binary()
    if not binary:
        raise AppError("FFMPEG_UNAVAILABLE", "缺少 FFmpeg，请重新运行安装脚本。", 503)
    command = [binary, "-hide_banner", "-v", "error", "-nostdin", "-xerror", "-protocol_whitelist", "file,pipe", "-format_whitelist", "mov",
               "-f", "mov", "-i", str(path),
               "-map", "0:v:0", "-map", "0:a?", "-f", "null", "-"]
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    started = time.monotonic()
    try:
        while process.poll() is None:
            check_cancelled()
            if time.monotonic() - started > timeout:
                raise AppError("VERIFY_TIMEOUT", "视频校验超时，请稍后重试。", 504)
            time.sleep(0.15)
        check_cancelled()
        if process.returncode != 0:
            raise AppError("INVALID_MEDIA", "下载文件无法完整解码，已清理不完整文件。", 422)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
