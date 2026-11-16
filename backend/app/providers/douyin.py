"""Anonymous Douyin playback resolver.

The site-specific signature is intentionally kept in this adapter.  It follows
https://github.com/yt-dlp/yt-dlp/pull/17826 and may need updating when Douyin changes
its web interface. No browser cookies or account credentials are read or saved.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import http.cookiejar
import http.client
import ipaddress
import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any


_BASE = "https://www.douyin.com/"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
_SHARE_HOSTS = frozenset({
    "v.douyin.com", "www.douyin.com", "douyin.com",
    "www.iesdouyin.com", "iesdouyin.com",
})
_MEDIA_DOMAINS = ("douyinvod.com", "douyin.com", "iesdouyin.com")
_SALT = "A96D855A08C0A9707F8BEF0D9A527E4E"
_TIMEOUT = 12.0
_RESOLVE_TIMEOUT = 60.0
_MAX_BODY = 4 * 1024 * 1024
_MAX_REDIRECTS = 6
_VIDEO_PATH = re.compile(r"^/(?:share/)?video/(\d{10,24})(?:/|$)")
_LINK = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_TRAILING_PUNCTUATION = ".,，。!?！？;；:：)]}）】》」』"


class ProviderError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class MediaFormat:
    id: str
    label: str
    width: int
    height: int
    codec: str
    bitrate: int
    size_bytes: int | None
    urls: list[str]


@dataclass
class ResolvedMedia:
    platform: str
    id: str
    title: str
    author: str
    cover_url: str | None
    duration: float
    source_url: str
    formats: list[MediaFormat]
    headers: dict[str, str]


def _validate_url(url: str, *, media: bool = False, check_dns: bool = True) -> str:
    """Accept only known public HTTPS destinations, including redirect targets."""
    if not isinstance(url, str) or len(url) > 16384 or any(ord(c) < 33 for c in url):
        raise ProviderError("invalid_url", "链接格式不正确，请重新复制分享链接。")
    try:
        parsed = urllib.parse.urlsplit(url)
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError as exc:
        raise ProviderError("invalid_url", "链接格式不正确，请重新复制分享链接。") from exc
    if (
        parsed.scheme.lower() != "https" or not host or parsed.username is not None
        or parsed.password is not None or port not in (None, 443) or "\\" in url
    ):
        raise ProviderError("invalid_url", "仅支持抖音的 HTTPS 分享链接。")
    permitted = (
        any(host == domain or host.endswith("." + domain) for domain in _MEDIA_DOMAINS)
        if media else host in _SHARE_HOSTS
    )
    if not permitted:
        raise ProviderError("unsupported_url", "当前仅支持抖音视频链接。")
    if check_dns:
        _public_addresses(host)
    # Drop fragments and normalize hostname without retaining user-supplied authority.
    return urllib.parse.urlunsplit(("https", host, parsed.path or "/", parsed.query, ""))


def _public_addresses(host: str) -> list[str]:
    try:
        addresses = list(dict.fromkeys(
            entry[4][0] for entry in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        ))
    except (socket.gaierror, OSError) as exc:
        raise ProviderError("network_error", "暂时无法连接抖音，请检查网络后重试。") from exc
    if not addresses or any(
        not ipaddress.ip_address(ip.split("%", 1)[0]).is_global for ip in addresses
    ):
        raise ProviderError("unsafe_url", "链接指向非公开网络地址，已停止请求。")
    return addresses


def validate_media_url(url: str) -> str:
    return _validate_url(url, media=True)


def _share_url(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ProviderError("invalid_input", "请粘贴抖音分享文案或视频链接。")
    if len(text) > 20000:
        raise ProviderError("invalid_input", "分享内容过长，请只粘贴这一条作品的分享文案。")
    candidates = _LINK.findall(text.replace("\u200b", "").replace("\ufeff", ""))
    for candidate in candidates:
        candidate = candidate.rstrip(_TRAILING_PUNCTUATION)
        try:
            return _validate_url(candidate, check_dns=False)
        except ProviderError:
            continue
    if candidates:
        raise ProviderError("unsupported_url", "当前仅支持抖音 HTTPS 视频链接。")
    raise ProviderError("invalid_input", "没有找到视频链接，请复制完整的抖音分享文案。")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    """Pin a freshly validated address while retaining host-based TLS/SNI checks."""

    def https_open(self, req):
        checked_url = _validate_url(req.full_url, check_dns=False)
        host = urllib.parse.urlsplit(checked_url).hostname
        addresses = _public_addresses(host)

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
                        # Literal checked IP; HTTPSConnection keeps the original
                        # hostname for TLS certificate validation and SNI.
                        return socket.create_connection((ip, 443), remaining, source_address)
                    except OSError as exc:
                        last_error = exc
                raise last_error or OSError("No public destination")

            connection._create_connection = connect_checked
            return connection

        return self.do_open(connection_factory, req, context=self._context)


class _Client:
    def __init__(self):
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect(), _PinnedHTTPSHandler(),
            urllib.request.HTTPCookieProcessor(self.cookies),
        )
        self.deadline = time.monotonic() + _RESOLVE_TIMEOUT

    def _timeout(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ProviderError("network_timeout", "解析超时，请稍后重试。")
        return min(_TIMEOUT, remaining)

    def request(
        self, url: str, *, data: bytes | None = None,
        extra_headers: dict[str, str] | None = None,
        stop_at_video: bool = False,
    ) -> tuple[bytes, Any, str]:
        headers = {"User-Agent": _USER_AGENT, "Referer": _BASE, **(extra_headers or {})}
        for hop in range(_MAX_REDIRECTS + 1):
            url = _validate_url(url)
            if stop_at_video and _VIDEO_PATH.match(urllib.parse.urlsplit(url).path):
                return b"", {}, url
            req = urllib.request.Request(url, data=data, headers=headers)
            try:
                with self.opener.open(req, timeout=self._timeout()) as response:
                    chunks: list[bytes] = []
                    size = 0
                    while True:
                        remaining = self._timeout()
                        # urllib's response owns the connected SSL socket. Update
                        # its timeout as the overall parsing deadline approaches.
                        raw = getattr(getattr(response, "fp", None), "raw", None)
                        sock = getattr(raw, "_sock", None)
                        if sock is not None:
                            sock.settimeout(remaining)
                        # read1 performs at most one buffered/raw read, so a slow
                        # trickle cannot keep one read(n) alive indefinitely.
                        chunk = response.read1(min(64 * 1024, _MAX_BODY + 1 - size))
                        self._timeout()
                        if not chunk:
                            break
                        chunks.append(chunk)
                        size += len(chunk)
                        if size > _MAX_BODY:
                            raise ProviderError("upstream_changed", "抖音返回了无法解析的内容，请稍后重试。")
                    return b"".join(chunks), response.headers, url
            except urllib.error.HTTPError as exc:
                if exc.code in (301, 302, 303, 307, 308):
                    location = exc.headers.get("Location")
                    exc.close()
                    if not location or hop == _MAX_REDIRECTS:
                        raise ProviderError("redirect_error", "分享链接跳转异常，请重新复制作品链接。")
                    url = urllib.parse.urljoin(url, location)
                    if exc.code in (301, 302, 303):
                        data = None
                        headers.pop("Content-Type", None)
                    continue
                code = exc.code
                exc.close()
                if code in (401, 403, 429):
                    raise ProviderError("verification_required", "抖音暂时要求验证或限制了请求，请稍后重试。") from None
                if code in (404, 410):
                    raise ProviderError("not_found", "作品无法访问，可能已删除或设置了访问权限。") from None
                raise ProviderError("upstream_error", "抖音服务暂时不可用，请稍后重试。") from None
            except (TimeoutError, socket.timeout):
                raise ProviderError("network_timeout", "解析超时，请检查网络后重试。") from None
            except (urllib.error.URLError, OSError):
                raise ProviderError("network_error", "连接抖音失败，请检查网络后重试。") from None
        raise ProviderError("redirect_error", "分享链接跳转次数过多，请重新复制作品链接。")

    def video_id(self, text: str) -> str:
        url = _share_url(text)
        match = _VIDEO_PATH.match(urllib.parse.urlsplit(url).path)
        if match:
            return match.group(1)
        if urllib.parse.urlsplit(url).hostname != "v.douyin.com":
            raise ProviderError("unsupported_content", "请粘贴单条抖音视频的分享链接，暂不支持主页、图集或直播。")
        _, _, final_url = self.request(url, stop_at_video=True)
        match = _VIDEO_PATH.match(urllib.parse.urlsplit(final_url).path)
        if not match:
            raise ProviderError("unsupported_content", "该分享链接没有指向可下载的视频作品。")
        return match.group(1)

    def _cookie(self, name: str, value: str) -> None:
        self.cookies.set_cookie(http.cookiejar.Cookie(
            0, name, value, None, False, ".douyin.com", True, True,
            "/", True, True, None, True, None, None, {},
        ))

    def detail(self, video_id: str) -> dict[str, Any]:
        self.request(
            _BASE + "ttwid/register",
            data=json.dumps({"aid": 6383, "service": "www.douyin.com"}).encode(),
            extra_headers={"Content-Type": "application/json"},
        )
        if not any(cookie.name == "ttwid" for cookie in self.cookies):
            raise ProviderError("verification_required", "暂时无法建立抖音匿名会话，请稍后重试。")
        self._cookie("passport_csrf_token", uuid.uuid4().hex)
        _, headers, _ = self.request(_BASE)
        uifid = next((
            cookie.value for cookie in self.cookies
            if cookie.name.lower() in ("uifid", "uifid_temp", "uifidtemp")
        ), None) or headers.get("x-tt-trace-host")
        if not uifid:
            raise ProviderError("verification_required", "抖音暂时要求验证，当前无法获取公开播放信息。")
        timestamp = str(int(time.time()))
        query = {"aweme_id": video_id, "aid": 6383, "uifid": uifid, "timestamp": timestamp}
        digest_input = f"{uifid}_{timestamp}_{_SALT}_{urllib.parse.urlencode(query)}"
        query["x-secsdk-web-signature"] = hashlib.md5(digest_input.encode()).hexdigest()
        body, _, _ = self.request(_BASE + "aweme/v1/web/aweme/detail/?" + urllib.parse.urlencode(query))
        if not body.strip() or body.lstrip().startswith(b"<"):
            raise ProviderError("verification_required", "抖音暂时限制了播放信息请求，请稍后重试。")
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            raise ProviderError("upstream_changed", "抖音返回的数据格式发生变化，暂时无法解析。") from None
        if not isinstance(payload, dict):
            raise ProviderError("upstream_changed", "抖音返回的数据格式发生变化，暂时无法解析。")
        detail = payload.get("aweme_detail")
        if not isinstance(detail, dict) or not detail:
            if payload.get("status_code") not in (0, None):
                raise ProviderError("upstream_error", "抖音暂未返回作品信息，请稍后重试。")
            raise ProviderError("not_found", "作品无法访问，可能已删除、设为私密或不再公开。")
        return detail


def _positive_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (ValueError, TypeError, OverflowError):
        return 0


def _candidate_urls(address: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for value in address.get("url_list", []) or []:
        if not isinstance(value, str):
            continue
        try:
            url = _validate_url(value, media=True, check_dns=False)
        except ProviderError:
            continue
        if url not in urls:
            urls.append(url)
    return urls


def _parse_detail(detail: dict[str, Any], video_id: str) -> ResolvedMedia:
    actual_id = str(detail.get("aweme_id", video_id))
    if actual_id != video_id:
        raise ProviderError("upstream_changed", "返回的作品与分享链接不一致，已停止解析。")
    video = detail.get("video")
    if not isinstance(video, dict):
        raise ProviderError("unsupported_content", "该作品不是可下载的视频，暂不支持图集或直播。")
    duration = _positive_int(video.get("duration") or detail.get("duration")) / 1000
    formats: list[MediaFormat] = []
    seen_files: set[str] = set()
    seen_variants: set[str] = set()

    def add(address: Any, variant: dict[str, Any], *, fallback_codec: str = "h264") -> None:
        if not isinstance(address, dict):
            return
        urls = _candidate_urls(address)
        if not urls:
            return
        # The outer video.width/height may describe the uploaded master. Only
        # report dimensions of the actual selectable playback stream.
        width, height = _positive_int(address.get("width")), _positive_int(address.get("height"))
        codec = "h265" if variant.get("is_h265") or variant.get("is_bytevc1") else fallback_codec
        bitrate = _positive_int(variant.get("bit_rate"))
        size = _positive_int(address.get("data_size")) or None
        file_hash = str(address.get("file_hash") or "")
        gear = str(variant.get("gear_name") or "default")
        quality = str(variant.get("quality_type") or "")
        key = f"{width}:{height}:{codec}:{gear}:{quality}:{bitrate}"
        if (file_hash and file_hash in seen_files) or key in seen_variants:
            return
        if file_hash:
            seen_files.add(file_hash)
        seen_variants.add(key)
        fmt_id = "dy-" + hashlib.sha256(key.encode()).hexdigest()[:16]
        edge = min(width, height)
        dimensions = f"{edge}p" if edge else "播放版本"
        codec_label = "H.265" if codec == "h265" else "H.264"
        rate_label = f" · {bitrate / 1_000_000:.2f} Mbps" if bitrate else ""
        formats.append(MediaFormat(fmt_id, f"{dimensions} · {codec_label}{rate_label}",
                                   width, height, codec, bitrate, size, urls))

    for variant in video.get("bit_rate", []) or []:
        if isinstance(variant, dict):
            add(variant.get("play_addr"), variant)
    # Fallbacks allow videos without bit_rate while excluding download_addr,
    # which can add platform watermark/suffix logos.
    for field, codec in (("play_addr_h264", "h264"), ("play_addr", "h264"), ("play_addr_265", "h265")):
        add(video.get(field), {}, fallback_codec=codec)
    if not formats:
        raise ProviderError("no_playable_format", "没有找到可用的公开播放版本，作品可能不支持当前下载方式。")
    formats.sort(key=lambda f: (f.width * f.height, f.codec == "h264", f.bitrate), reverse=True)
    title = str(detail.get("desc") or "抖音视频").strip()[:500]
    author_obj = detail.get("author")
    author = str(author_obj.get("nickname") or "未知作者")[:100] if isinstance(author_obj, dict) else "未知作者"
    return ResolvedMedia(
        "douyin", video_id, title or "抖音视频", author, None, duration,
        f"https://www.douyin.com/video/{video_id}", formats,
        {"User-Agent": _USER_AGENT, "Referer": _BASE},
    )


def resolve(text: str) -> ResolvedMedia:
    client = _Client()
    video_id = client.video_id(text)
    return _parse_detail(client.detail(video_id), video_id)


def public_media(media: ResolvedMedia) -> dict[str, Any]:
    data = asdict(media)
    data.pop("headers", None)
    for fmt in data["formats"]:
        fmt.pop("urls", None)
    return data
