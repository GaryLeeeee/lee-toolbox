# Lee Toolbox API contract

All paths use `/api`. JSON errors: `{ "error": { "code": "...", "message": "中文可读说明" } }`. Dates are UTC ISO strings. First release is local only (127.0.0.1).

## Media
`POST /media/resolve` body `{ "text": "分享文案或链接" }` returns:
```json
{
  "platform": "douyin", "id": "7444165186107297074", "title": "标题", "author": "作者",
  "cover_url": null, "duration": 66.92, "source_url": "https://www.douyin.com/video/7444165186107297074",
  "formats": [{ "id": "stable-format-id", "label": "720p · H.264", "width": 720, "height": 1280, "codec": "h264", "bitrate": 1050807, "size_bytes": 8790134 }]
}
```
`cover_url` is optional/null. Signed media URLs and request headers remain backend-private. Resolve may take tens of seconds. UI must show loading, error and retry states. Default format is first, sorted by resolution then preference/bitrate.

## Tasks
- `POST /tasks` body `{ "source_text": "...", "format_id": "..." }` returns Task (HTTP 201). format_id optional.
- `GET /tasks` returns `{ "items": [Task] }`, newest first. Optional `status` filter.
- `GET /tasks/{id}` returns Task.
- `POST /tasks/{id}/cancel` returns Task. Completed tasks cannot be cancelled.
- `POST /tasks/{id}/retry` returns a NEW Task (HTTP 201), preserving original history. Failed/cancelled/interrupted tasks can retry.
- `GET /tasks/{id}/file` downloads a completed file. Missing/non-complete returns structured error.
- `GET /health` returns `{ "status": "ok", "worker_running": true, "ffmpeg_available": true }`.

Task fields:
```json
{
 "id": "uuid", "tool_id": "video-download", "status": "queued", "title": "待解析视频", "author": "",
 "source_text": "分享文字", "format_id": null, "format_label": "自动选择",
 "progress": 0, "downloaded_bytes": 0, "total_bytes": null, "speed_bps": null,
 "file_name": null, "file_size": null, "file_available": false,
 "error": null, "created_at": "2026-11-16T00:00:00Z", "updated_at": "2026-11-16T00:00:00Z"
}
```
Statuses: queued, resolving, downloading, verifying, completed, failed, cancelled, interrupted. Progress is 0..100. Error is null or `{code,message}`. Active statuses: queued/resolving/downloading/verifying. Lists may be polled every 1.5–2 seconds, and page visibility should be respected.

## Provider Python interface (backend/app/providers/douyin.py)
Define `ProviderError(code: str, message: str)` with `.code` and `.message`.
Define dataclass `MediaFormat(id,label,width,height,codec,bitrate,size_bytes,urls: list[str])`.
Define dataclass `ResolvedMedia(platform,id,title,author,cover_url,duration,source_url,formats: list[MediaFormat],headers: dict[str,str])`.
`resolve(text: str) -> ResolvedMedia` is synchronous, bounded HTTP timeouts; no browser/account cookies. `public_media(media)` returns above public JSON (omit urls and headers).
`validate_media_url(url: str) -> str` validates allowed public HTTPS media host, returns URL or raises ProviderError. Downloader must revalidate every redirect and reject private IP destinations. Expose `open_media(url, headers, timeout=...)` only if convenient; API implementer can own network policy with provider helper.

## Backend conventions
SQLite defaults to repo `data/toolbox.db`; downloads in `data/downloads/`, temporary files in `data/tmp/`. Override base via LEE_TOOLBOX_DATA_DIR. FastAPI `app.main:app`. Worker launched as separate child process in lifespan, terminating cleanly on shutdown; interrupted running tasks are marked interrupted, queued tasks retained. SQLite atomic claim, one worker. `LEE_TOOLBOX_WORKER=0` disables worker for tests. Backend owns subprocess FFmpeg discovery using system binary then imageio_ffmpeg fallback. Serve frontend/dist if present, excluding `/api` and rejecting traversal. Tests may use mocked providers/local generated media; real URLs are opt-in integration checks.
