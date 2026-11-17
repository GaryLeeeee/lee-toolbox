"""Anonymous Xiaohongshu note resolver; never executes JavaScript or reads cookies.

Original image keys are exposed in imageList[].fileId. Public H5 image URLs are
not original-image sources. Video exports retain and disclose source watermarks.
Resource layouts are also documented by XHS-Downloader's image/video adapters:
https://github.com/JoeanAmier/XHS-Downloader/tree/master/source/application
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import http.client
import http.cookiejar
import ipaddress
import json
import math
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Literal


_BASE = "https://www.xiaohongshu.com/"
_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"
)
_SHARE_HOSTS = frozenset({
    "xhslink.cn", "www.xhslink.cn", "xhslink.com", "www.xhslink.com",
    "xiaohongshu.com", "www.xiaohongshu.com",
})
_TIMEOUT = 12.0
_RESOLVE_TIMEOUT = 60.0
_MAX_BODY = 4 * 1024 * 1024
_MAX_REDIRECTS = 6
_NOTE_PATH = re.compile(r"^/(?:explore|discovery/item)/([a-fA-F0-9]{24})(?:/)?$")
_LINK = re.compile(r"https?(?:\\)?://[^\s<>\"']+", re.IGNORECASE)
_TRAILING_PUNCTUATION = ".,，。!?！？;；:：)]}）】》」』"
_RESOURCE_KEY = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*")
_STATE_ASSIGNMENT = re.compile(r"(?:window\.)?__INITIAL_STATE__\s*=\s*")
_JSON_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|\bundefined\b', re.DOTALL)
_NO_WATERMARK_DESCRIPTION = re.compile(r"(?:^|_)(?:NO|WITHOUT)_WATERMARK(?=_|$)")


class ProviderError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class XhsAsset:
    id: str
    kind: str
    label: str
    width: int
    height: int
    duration: float | None
    image_urls: list[str]
    video_urls: list[str]
    available: bool = True
    unavailable_reason: str | None = None
    watermark_status: Literal["none", "present", "unknown"] = "unknown"


@dataclass
class ResolvedNote:
    platform: str
    id: str
    title: str
    author: str
    source_url: str
    assets: list[XhsAsset]
    warnings: list[str]
    headers: dict[str, str]


def _public_addresses(host: str) -> list[str]:
    try:
        addresses = list(dict.fromkeys(
            entry[4][0] for entry in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        ))
    except OSError as exc:
        raise ProviderError("network_error", "暂时无法连接小红书，请检查网络后重试。") from exc
    if not addresses or any(
        not ipaddress.ip_address(ip.split("%", 1)[0]).is_global for ip in addresses
    ):
        raise ProviderError("unsafe_url", "链接指向非公开网络地址，已停止请求。")
    return addresses


def _validate_url(url: str, *, media: bool = False, check_dns: bool = True) -> str:
    if not isinstance(url, str) or len(url) > 16384 or any(ord(c) < 33 for c in url):
        raise ProviderError("invalid_url", "链接格式不正确，请重新复制分享链接。")
    try:
        parsed = urllib.parse.urlsplit(url)
        host, port = (parsed.hostname or "").lower(), parsed.port
    except ValueError as exc:
        raise ProviderError("invalid_url", "链接格式不正确，请重新复制分享链接。") from exc
    if (parsed.scheme.lower() != "https" or not host or "\\" in url
            or parsed.username is not None or parsed.password is not None
            or port not in (None, 443)):
        raise ProviderError("invalid_url", "仅支持小红书的 HTTPS 分享链接。")
    allowed = (
        host == "xhscdn.com" or host.endswith(".xhscdn.com") or host == "ci.xiaohongshu.com"
    ) if media else host in _SHARE_HOSTS
    if not allowed:
        raise ProviderError("unsupported_url", "链接不是受支持的小红书地址。")
    if check_dns:
        _public_addresses(host)
    return urllib.parse.urlunsplit(("https", host, parsed.path or "/", parsed.query, ""))


def validate_media_url(url: str) -> str:
    """Validate a media destination; download transports must pin the checked IP."""
    return _validate_url(url, media=True)


def _official_https(url: str, *, media: bool = False) -> str:
    # Only URLs returned by the platform enter here. Validate authority before
    # upgrading legacy official HTTP redirects/media; never transmit HTTP.
    if isinstance(url, str) and url.lower().startswith("http://"):
        url = "https://" + url[7:]
    return _validate_url(url, media=media, check_dns=False)


def _share_url(text: str) -> str:
    if not isinstance(text, str) or not text.strip() or len(text) > 20000:
        raise ProviderError("invalid_input", "请粘贴一条小红书分享文案或笔记链接。")
    candidates = _LINK.findall(text.replace("\u200b", "").replace("\ufeff", ""))
    for candidate in candidates:
        try:
            # Some copied Markdown escapes the scheme's colon. Only normalize
            # that escape; backslashes in the host/path remain invalid.
            candidate = re.sub(r"^(https?)\\:", r"\1:", candidate, flags=re.IGNORECASE)
            return _validate_url(candidate.rstrip(_TRAILING_PUNCTUATION), check_dns=False)
        except ProviderError:
            continue
    if candidates:
        raise ProviderError("unsupported_url", "当前仅支持小红书 HTTPS 笔记分享链接。")
    raise ProviderError("invalid_input", "没有找到链接，请复制完整的小红书分享文案。")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        url = _validate_url(req.full_url, check_dns=False)
        addresses = _public_addresses(urllib.parse.urlsplit(url).hostname)

        def connection_factory(connection_host, **kwargs):
            connection = http.client.HTTPSConnection(connection_host, **kwargs)

            def connect_checked(address, timeout=_TIMEOUT, source_address=None, **unused):
                deadline = time.monotonic() + (timeout if isinstance(timeout, (int, float)) else _TIMEOUT)
                last_error = None
                for ip in addresses:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("Connection deadline exceeded")
                    try:
                        return socket.create_connection((ip, 443), remaining, source_address)
                    except OSError as exc:
                        last_error = exc
                raise last_error or OSError("No public destination")

            connection._create_connection = connect_checked
            return connection

        return self.do_open(connection_factory, req, context=self._context)


class _Client:
    def __init__(self):
        # An in-memory anonymous session only; no browser/system cookie access.
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect(), _PinnedHTTPSHandler(),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        )
        self.deadline = time.monotonic() + _RESOLVE_TIMEOUT

    def _timeout(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ProviderError("network_timeout", "解析超时，请稍后重试。")
        return min(_TIMEOUT, remaining)

    def request(self, url: str, *, stop_at_note: bool = False) -> tuple[bytes, str]:
        for hop in range(_MAX_REDIRECTS + 1):
            url = _official_https(url)
            if stop_at_note and _NOTE_PATH.fullmatch(urllib.parse.urlsplit(url).path):
                return b"", url
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Referer": _BASE})
            try:
                with self.opener.open(req, timeout=self._timeout()) as response:
                    chunks: list[bytes] = []
                    size = 0
                    while True:
                        remaining = self._timeout()
                        raw = getattr(getattr(response, "fp", None), "raw", None)
                        sock = getattr(raw, "_sock", None)
                        if sock is not None:
                            sock.settimeout(remaining)
                        chunk = response.read1(min(64 * 1024, _MAX_BODY + 1 - size))
                        self._timeout()
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > _MAX_BODY:
                            raise ProviderError("upstream_changed", "小红书返回的页面过大，无法解析。")
                        chunks.append(chunk)
                    return b"".join(chunks), url
            except urllib.error.HTTPError as exc:
                status = exc.code
                location = exc.headers.get("Location")
                exc.close()
                if status in (301, 302, 303, 307, 308):
                    if not location or hop == _MAX_REDIRECTS:
                        raise ProviderError("redirect_error", "分享链接跳转异常，请重新复制笔记链接。") from None
                    url = _official_https(urllib.parse.urljoin(url, location))
                    continue
                if status in (401, 403, 429, 461, 471):
                    raise ProviderError("verification_required", "小红书暂时要求验证或限制了请求，请稍后重试。") from None
                if status in (404, 410):
                    raise ProviderError("not_found", "笔记无法访问，可能已删除或分享链接已失效。") from None
                raise ProviderError("upstream_error", "小红书服务暂时不可用，请稍后重试。") from None
            except (TimeoutError, socket.timeout):
                raise ProviderError("network_timeout", "解析超时，请检查网络后重试。") from None
            except (urllib.error.URLError, OSError):
                raise ProviderError("network_error", "连接小红书失败，请检查网络后重试。") from None
        raise ProviderError("redirect_error", "分享链接跳转次数过多，请重新复制笔记链接。")

    def note_url(self, text: str) -> tuple[str, str]:
        url = _share_url(text)
        parsed = urllib.parse.urlsplit(url)
        match = _NOTE_PATH.fullmatch(parsed.path)
        if not match:
            if parsed.hostname not in {"xhslink.cn", "www.xhslink.cn", "xhslink.com", "www.xhslink.com"}:
                raise ProviderError("unsupported_content", "请粘贴单条小红书笔记的分享链接，暂不支持主页或搜索页。")
            _, url = self.request(url, stop_at_note=True)
            parsed = urllib.parse.urlsplit(url)
            match = _NOTE_PATH.fullmatch(parsed.path)
        if not match or parsed.hostname not in {"xiaohongshu.com", "www.xiaohongshu.com"}:
            raise ProviderError("unsupported_content", "分享链接未指向可识别的小红书笔记。")
        note_id = match.group(1).lower()
        # Mobile SSR works anonymously where the desktop explore page may login.
        return note_id, urllib.parse.urlunsplit((
            "https", "www.xiaohongshu.com", f"/discovery/item/{note_id}", parsed.query, "",
        ))


def _initial_state(html: str) -> dict[str, Any]:
    match = _STATE_ASSIGNMENT.search(html)
    if not match:
        if re.search(r"captcha|验证码|访问频繁|登录后|请先登录|/login", html, re.IGNORECASE):
            raise ProviderError("verification_required", "当前分享页要求登录或验证，暂时无法匿名解析。请重新复制分享链接后重试。")
        raise ProviderError("upstream_changed", "分享页未提供笔记数据，可能已失效或平台页面发生变化。")
    script = re.split(r"</script\s*>", html[match.end():], maxsplit=1, flags=re.IGNORECASE)[0]
    # Match JSON strings atomically so literal words in titles remain unchanged.
    raw = _JSON_TOKEN.sub(lambda m: "null" if m.group() == "undefined" else m.group(), script)
    def invalid_constant(value):
        raise ValueError("Non-JSON constant")

    try:
        state, end = json.JSONDecoder(parse_constant=invalid_constant).raw_decode(raw.lstrip())
        if raw.lstrip()[end:].strip().rstrip(";").strip():
            raise ValueError("Executable text after JSON")
        if not isinstance(state, dict):
            raise ValueError("State must be an object")
        return state
    except (ValueError, RecursionError) as exc:
        raise ProviderError("upstream_changed", "小红书笔记数据格式暂不受支持，请稍后重试。") from exc


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _number(value: Any) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) and number >= 0 else 0
    except (TypeError, ValueError, OverflowError):
        return 0


def _key(value: Any) -> str | None:
    if isinstance(value, str) and 0 < len(value) <= 1024 and _RESOURCE_KEY.fullmatch(value):
        if all(part not in (".", "..") for part in value.split("/")):
            return value
    return None


def _image_key(image: dict) -> str | None:
    if key := _key(image.get("fileId") or image.get("file_id")):
        return key
    candidates = [image.get("urlDefault"), image.get("urlPre"), image.get("url")]
    infos = image.get("infoList")
    if isinstance(infos, list):
        candidates.extend(info.get("url") for info in infos if isinstance(info, dict))
    for url in candidates:
        try:
            parsed = urllib.parse.urlsplit(_official_https(url, media=True))
        except ProviderError:
            continue
        path = parsed.path.strip("/").split("!", 1)[0]
        # Web image paths have a date and signature ahead of the storage key.
        if parsed.hostname.startswith("sns-webpic-"):
            parts = path.split("/", 2)
            path = parts[2] if len(parts) == 3 else ""
        elif not (parsed.hostname.startswith("sns-img-") or parsed.hostname == "ci.xiaohongshu.com"):
            continue
        if key := _key(path):
            return key
    return None


def _image_urls(image: dict) -> list[str]:
    key = _image_key(image)
    return [f"https://{host}/{key}" for host in ("sns-img-bd.xhscdn.com", "sns-img-qc.xhscdn.com")] if key else []


def _media_urls(values: list[Any]) -> list[str]:
    result = []
    for value in values:
        try:
            url = _official_https(value, media=True)
        except ProviderError:
            continue
        if url not in result:
            result.append(url)
    return result


def _streams(stream: Any) -> list[dict]:
    if isinstance(stream, list):
        return [item for item in stream if isinstance(item, dict)]
    result = []
    for variants in _dict(stream).values():
        if isinstance(variants, list):
            result.extend(item for item in variants if isinstance(item, dict))
    return result


def _video_streams(video: dict) -> list[dict]:
    variants = _streams(_dict(video.get("media")).get("stream"))
    v2 = video.get("mediaV2")
    for media in v2 if isinstance(v2, list) else [v2]:
        media = _dict(media)
        variants.extend(_streams(media.get("stream")))
        if media.get("masterUrl"):
            variants.append(media)
    return variants


def _known_watermark(stream: dict) -> bool:
    description = str(stream.get("streamDesc", stream.get("stream_desc", ""))).upper()
    watermark_description = _NO_WATERMARK_DESCRIPTION.sub("_", description)
    backup = stream.get("backupUrls", stream.get("backup_urls", []))
    urls = [stream.get("masterUrl"), stream.get("master_url"), *(backup if isinstance(backup, list) else [])]
    # WEB_LIVEPHOTO_19 was checked against an actual public download: the logo
    # is burned into the bottom-right pixels. Codec alone says nothing about WM.
    return (
        "WEB_LIVEPHOTO_19" in description or _number(stream.get("streamType", stream.get("stream_type"))) == 19
        or any(stream.get(key) is True or stream.get(key) == 1 for key in ("hasWatermark", "watermark", "has_watermark"))
        or "WATERMARK" in watermark_description or "_WM" in watermark_description
        or any(isinstance(url, str)
               and re.match(r"^https?://[^/]+/stream/1/10/19/", url, re.IGNORECASE) for url in urls)
    )


def _clean_streams(stream: Any) -> tuple[list[str], dict, bool]:
    variants = _streams(stream)
    variants.sort(key=lambda item: (
        _number(item.get("width")) * _number(item.get("height")),
        _number(item.get("avgBitrate") or item.get("videoBitrate")), _number(item.get("size")),
    ), reverse=True)
    # Explicit no-watermark flags or an original stream descriptor are evidence;
    # merely being H.264/H.265 or having a masterUrl is not such a guarantee.
    for item in variants:
        description = str(item.get("streamDesc", item.get("stream_desc", ""))).upper()
        clean = any(item.get(key) is False or type(item.get(key)) is int and item[key] == 0
                    for key in ("hasWatermark", "watermark", "has_watermark"))
        clean = clean or bool(re.search(r"(?:^|_)ORIGINAL(?:_|$)|(?:^|_)ORIGIN(?:_|$)", description))
        clean = clean or bool(_NO_WATERMARK_DESCRIPTION.search(description))
        if _known_watermark(item) or not clean:
            continue
        backup = item.get("backupUrls", item.get("backup_urls", []))
        urls = _media_urls([item.get("masterUrl") or item.get("master_url"), *(backup if isinstance(backup, list) else [])])
        if urls:
            return urls, item, any(_known_watermark(v) for v in variants)
    return [], (variants[0] if variants else {}), any(_known_watermark(v) for v in variants)


def _original_video(video: dict) -> list[str]:
    consumer = _dict(video.get("consumer"))
    key = _key(consumer.get("originVideoKey") or consumer.get("origin_video_key")
               or video.get("originVideoKey") or video.get("origin_video_key"))
    return [f"https://sns-video-bd.xhscdn.com/{key}"] if key else _media_urls([
        consumer.get("originVideoUrl"), video.get("originVideoUrl"), video.get("origin_video_url"),
    ])


def _export_video(video: dict, stream: Any) -> tuple[list[str], dict, str]:
    """Prefer declared originals/clean streams, retaining source watermark status."""
    urls, best, _ = _clean_streams(stream)
    original = _original_video(video)
    original_watermarked = _known_watermark({"backupUrls": original})
    if original and not original_watermarked:
        return original, best, "none"
    if urls:
        return urls, best, "none"
    if original:
        return original, best, "present"
    variants = sorted(_streams(stream), key=lambda item: (
        _number(item.get("width")) * _number(item.get("height")),
        _number(item.get("avgBitrate") or item.get("videoBitrate")), _number(item.get("size")),
    ), reverse=True)
    for item in variants:
        backup = item.get("backupUrls", item.get("backup_urls", []))
        urls = _media_urls([item.get("masterUrl") or item.get("master_url"),
                            *(backup if isinstance(backup, list) else [])])
        if urls:
            return urls, item, "present" if _known_watermark(item) else "unknown"
    return [], best, "unknown"


def _asset_id(note_id: str, kind: str, index: int, image_key: str | None = None) -> str:
    identity = f"{note_id}:{kind}:{index}:{image_key or ''}"
    return f"{kind}-{hashlib.sha256(identity.encode()).hexdigest()[:20]}"


def _assert_note_identity(note: dict, note_id: str) -> None:
    identities = [note[key] for key in ("noteId", "id", "note_id") if note.get(key)]
    if not identities or any(not isinstance(value, str) or value.lower() != note_id for value in identities):
        raise ProviderError("upstream_changed", "返回的笔记与分享链接不一致，已停止解析。")


def _find_note(state: dict, note_id: str) -> dict:
    mobile = _dict(_dict(_dict(state.get("noteData")).get("data")).get("noteData"))
    desktop = _dict(_dict(_dict(_dict(state.get("note")).get("noteDetailMap")).get(note_id)).get("note"))
    note = mobile or desktop
    if not note:
        raise ProviderError("verification_required", "未取得公开笔记内容，分享链接可能已过期或需要验证，请重新分享后重试。")
    _assert_note_identity(note, note_id)
    return note


def _parse_note(note: dict, note_id: str) -> ResolvedNote:
    _assert_note_identity(note, note_id)
    images = note.get("imageList", note.get("images_list", []))
    images = [item for item in images if isinstance(item, dict)] if isinstance(images, list) else []
    if len(images) > 100:
        raise ProviderError("unsupported_content", "笔记资源数量超过支持上限。")
    assets, warnings = [], []
    note_type = note.get("type") or ("video" if note.get("video") else "normal")
    if note_type == "video":
        video = _dict(note.get("video"))
        media = _dict(video.get("media"))
        urls, best, watermark_status = _export_video(video, _video_streams(video))
        original = _original_video(video)
        reason = None if urls else "公开页面未提供可下载的视频源。"
        assets.append(XhsAsset(
            _asset_id(note_id, "video", 0), "video", "视频",
            int(_number(media.get("width") if original else best.get("width"))),
            int(_number(media.get("height") if original else best.get("height"))),
            (_number(best.get("duration")) / 1000 or _number(_dict(video.get("capa")).get("duration")) or None),
            _image_urls(images[0]) if images else [], urls, bool(urls), reason, watermark_status,
        ))
    elif note_type in ("normal", "image"):
        for index, item in enumerate(images, 1):
            image_urls = _image_urls(item)
            live_data = _dict(item.get("livePhoto") or item.get("live_photo"))
            stream = item.get("stream") or _dict(live_data.get("media")).get("stream")
            is_live = bool(item.get("livePhoto") or item.get("live_photo") or _streams(stream))
            reason = None if image_urls else "公开页面未提供可下载的无平台水印原图。"
            assets.append(XhsAsset(
                _asset_id(note_id, "image", index, _image_key(item)), "image",
                f"Live 图 {index} · 静态原图" if is_live else f"图片 {index}",
                int(_number(item.get("width"))), int(_number(item.get("height"))),
                None, image_urls, [], bool(image_urls), reason, "none" if image_urls else "unknown",
            ))
            if is_live:
                video_urls, best, watermark_status = _export_video(live_data, stream)
                assets.append(XhsAsset(
                    _asset_id(note_id, "video", index, _image_key(item)), "video",
                    f"Live 图 {index} · 动态视频",
                    int(_number(best.get("width") or item.get("width"))),
                    int(_number(best.get("height") or item.get("height"))),
                    _number(best.get("duration")) / 1000 or None,
                    image_urls, video_urls, bool(video_urls),
                    None if video_urls else "公开页面未提供可下载的 Live 动态片段。", watermark_status,
                ))
    else:
        raise ProviderError("unsupported_content", "暂不支持这类小红书笔记。")
    if not assets:
        raise ProviderError("unsupported_content", "笔记中没有找到可导出的图片或视频。")
    if any(not asset.available for asset in assets):
        warnings.append("部分资源未提供可下载的源文件，已标记为不可导出。")
    if any(asset.label.endswith("· 静态原图") for asset in assets):
        warnings.append("暂不支持直接导出 Live Photo。Live 图已拆为独立的静态图片和 MP4 视频，可分别选择；不会生成相册 Live Photo 配对文件。")
    if any(asset.available and asset.watermark_status == "present" for asset in assets):
        warnings.append("部分视频源已含平台水印，导出会保留水印。")
    if any(asset.available and asset.kind == "video" and asset.watermark_status == "unknown" for asset in assets):
        warnings.append("部分视频源的水印情况未确认，导出会保留源文件画面。")
    return ResolvedNote(
        "xiaohongshu", note_id, str(note.get("title") or "未命名笔记")[:500],
        str(_dict(note.get("user")).get("nickname") or _dict(note.get("user")).get("nickName") or "未知作者")[:200],
        f"https://www.xiaohongshu.com/explore/{note_id}", assets, warnings,
        {"User-Agent": _USER_AGENT, "Referer": _BASE},
    )


def resolve(text: str) -> ResolvedNote:
    client = _Client()
    note_id, url = client.note_url(text)
    body, final_url = client.request(url)
    parsed = urllib.parse.urlsplit(final_url)
    match = _NOTE_PATH.fullmatch(parsed.path)
    if not match or match.group(1).lower() != note_id:
        raise ProviderError("verification_required", "分享页要求登录或验证，暂时无法匿名解析。")
    state = _initial_state(body.decode("utf-8", errors="replace"))
    return _parse_note(_find_note(state, note_id), note_id)


def public_note(note: ResolvedNote) -> dict:
    return {
        "platform": note.platform, "id": note.id, "title": note.title,
        "author": note.author, "source_url": note.source_url, "warnings": note.warnings,
        "assets": [{
            "id": asset.id, "kind": asset.kind, "label": asset.label,
            "width": asset.width, "height": asset.height, "duration": asset.duration,
            "available": asset.available, "unavailable_reason": asset.unavailable_reason,
            "watermark_status": asset.watermark_status,
            "preview_url": None,
        } for asset in note.assets],
    }
