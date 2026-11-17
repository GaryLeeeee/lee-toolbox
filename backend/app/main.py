from contextlib import asynccontextmanager
import asyncio
import os
from pathlib import Path
import subprocess
import sys
import threading
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError
from app.core.settings import get_settings
from app.services.files import FILE_TYPES, public_task, require_task_file
from app.services.media import ffmpeg_binary
from app.services.previews import PreviewRegistry, fetch_preview
from app.storage.database import Store, STATUSES

resolve_slots = threading.BoundedSemaphore(2)
preview_slots = threading.BoundedSemaphore(4)


class ResolveInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=5000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("empty")
        return value.strip()


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool_id: Literal["video-download", "xiaohongshu-export"] = "video-download"
    source_text: str = Field(min_length=1, max_length=5000)
    format_id: str | None = Field(default=None, min_length=1, max_length=160)
    asset_ids: list[str] | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("source_text")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("empty")
        return value.strip()

    @field_validator("asset_ids")
    @classmethod
    def valid_selection(cls, value):
        if value is not None and (any(not item.strip() or len(item) > 160 for item in value)
                                  or len(set(value)) != len(value)):
            raise ValueError("Invalid selection")
        return value

    @model_validator(mode="after")
    def compatible_tool(self):
        if ((self.tool_id == "video-download" and self.asset_ids is not None)
                or (self.tool_id == "xiaohongshu-export" and self.format_id is not None)):
            raise ValueError("Tool options do not match")
        return self


def error_response(code, message, status_code):
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status_code)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.prepare()
    store = Store(settings.db_path)
    store.initialize()
    app.state.settings = settings
    app.state.store = store
    app.state.previews = PreviewRegistry()
    app.state.worker = None
    if settings.worker_enabled:
        app.state.worker = subprocess.Popen([sys.executable, "-m", "app.jobs.worker"], cwd=Path(__file__).resolve().parents[1])
    try:
        yield
    finally:
        process = app.state.worker
        if process and process.poll() is None:
            process.terminate()
            try:
                await asyncio.to_thread(process.wait, timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                await asyncio.to_thread(process.wait)


app = FastAPI(title="Lee Toolbox", version="0.1.0", lifespan=lifespan,
              docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)


@app.middleware("http")
async def local_access(request: Request, call_next):
    # Prevent DNS rebinding and requests from unrelated websites to this local service.
    try:
        host = urlsplit("http://" + request.headers.get("host", ""))
        if host.hostname not in {"localhost", "127.0.0.1", "::1"} or host.username or host.password:
            return error_response("INVALID_HOST", "此服务仅接受本机访问。", 403)
        request_port = host.port or 80
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin:
                parsed = urlsplit(origin)
                origin_port = parsed.port or (443 if parsed.scheme == "https" else 80)
                if (parsed.scheme not in {"http", "https"} or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                        or parsed.username or parsed.password or parsed.path not in {"", "/"}
                        or origin_port not in {request_port, int(os.environ.get("LEE_TOOLBOX_WEB_PORT", "5173"))}):
                    return error_response("INVALID_ORIGIN", "请从本机工具箱页面发起操作。", 403)
            elif request.headers.get("sec-fetch-site") == "cross-site":
                return error_response("INVALID_ORIGIN", "请从本机工具箱页面发起操作。", 403)
    except ValueError:
        return error_response("INVALID_HOST", "请求地址格式不正确。", 403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(AppError)
async def app_error_handler(request, exc):
    return error_response(exc.code, exc.message, exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_handler(request, exc):
    return error_response("INVALID_INPUT", "请求参数不完整或格式不正确，请检查输入内容。", 422)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request, exc):
    return error_response("NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR",
                          "请求的资源不存在。" if exc.status_code == 404 else "请求无法处理。", exc.status_code)


@app.get("/api/health")
def health(request: Request):
    process = request.app.state.worker
    return {"status": "ok", "worker_running": bool(process and process.poll() is None),
            "ffmpeg_available": ffmpeg_binary() is not None}


@app.post("/api/media/resolve")
def resolve_media(body: ResolveInput):
    from app.providers.douyin import resolve, public_media, ProviderError
    if not resolve_slots.acquire(blocking=False):
        raise AppError("RESOLVE_BUSY", "正在解析其他视频，请稍后重试。", 429)
    try:
        return public_media(resolve(body.text))
    except ProviderError as exc:
        raise AppError(exc.code, exc.message, 422) from exc
    finally:
        resolve_slots.release()


@app.post("/api/xhs/resolve")
def resolve_xiaohongshu(body: ResolveInput, request: Request):
    from app.providers.xiaohongshu import resolve, public_note, ProviderError
    if not resolve_slots.acquire(blocking=False):
        raise AppError("RESOLVE_BUSY", "正在解析其他作品，请稍后重试。", 429)
    try:
        note = resolve(body.text)
        result = public_note(note)
        assets = {asset.id: asset for asset in note.assets}
        for item in result["assets"]:
            item["preview_url"] = request.app.state.previews.register(assets[item["id"]].image_urls, note.headers)
        return result
    except ProviderError as exc:
        raise AppError(exc.code, exc.message, 422) from exc
    finally:
        resolve_slots.release()


@app.get("/api/xhs/previews/{token}")
def image_preview(token: str, request: Request):
    preview = request.app.state.previews.get(token)
    if not preview_slots.acquire(blocking=False):
        raise AppError("PREVIEW_BUSY", "正在加载其他预览，请稍后重试。", 429)
    try:
        data, mime = fetch_preview(preview)
        return Response(data, media_type=mime, headers={"Content-Security-Policy": "default-src 'none'"})
    finally:
        preview_slots.release()


@app.post("/api/tasks", status_code=201)
def create_task(body: TaskInput, request: Request):
    settings = request.app.state.settings
    task = request.app.state.store.create(body.source_text, body.format_id, settings.max_active_tasks,
                                          tool_id=body.tool_id, asset_ids=body.asset_ids)
    return public_task(task, settings.downloads_dir)


@app.get("/api/tasks")
def list_tasks(request: Request, status: str | None = None):
    if status is not None and status not in STATUSES:
        raise AppError("INVALID_STATUS", "任务状态不正确。", 422)
    return {"items": [public_task(task, request.app.state.settings.downloads_dir)
                      for task in request.app.state.store.list(status)]}


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str, request: Request):
    return public_task(request.app.state.store.get(task_id), request.app.state.settings.downloads_dir)


@app.post("/api/tasks/{task_id}/cancel")
def cancel_task(task_id: str, request: Request):
    return public_task(request.app.state.store.cancel(task_id), request.app.state.settings.downloads_dir)


@app.post("/api/tasks/{task_id}/retry", status_code=201)
def retry_task(task_id: str, request: Request):
    settings = request.app.state.settings
    task = request.app.state.store.retry(task_id, settings.max_active_tasks)
    return public_task(task, settings.downloads_dir)


@app.get("/api/tasks/{task_id}/file")
def download_file(task_id: str, request: Request):
    task = request.app.state.store.get(task_id)
    path = require_task_file(task, request.app.state.settings.downloads_dir)
    # User-facing filename omits the UUID used for collision-free local storage.
    name = path.name.removeprefix(task["id"] + "_")
    return FileResponse(path, media_type=FILE_TYPES.get(path.suffix.lower(), "application/octet-stream"), filename=name)


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str, request: Request):
    if path == "api" or path.startswith("api/"):
        raise AppError("NOT_FOUND", "请求的接口不存在。", 404)
    if "\\" in path or any(part in {"..", "."} for part in path.split("/")):
        raise AppError("NOT_FOUND", "请求的资源不存在。", 404)
    root = request.app.state.settings.frontend_dir.resolve()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise AppError("NOT_FOUND", "请求的资源不存在。", 404)
    if candidate.is_file():
        return FileResponse(candidate)
    if path.startswith("assets/") or Path(path).suffix:
        raise AppError("NOT_FOUND", "请求的资源不存在。", 404)
    index = root / "index.html"
    if index.is_file():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return JSONResponse({"name": "Lee Toolbox", "message": "前端尚未构建，请运行 scripts/build.sh；开发模式请打开 http://127.0.0.1:5173。"})
