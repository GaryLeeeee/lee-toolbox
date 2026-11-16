"""Bounded public HTTPS requests, with destination IP pinned after DNS validation."""
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit, urljoin

from app.core.errors import AppError

MEDIA_DOMAINS = ("douyinvod.com", "douyin.com", "iesdouyin.com", "bytecdn.cn", "snssdk.com", "byteimg.com")


def public_destination(url: str):
    try:
        parts = urlsplit(url)
        hostname = (parts.hostname or "").lower().rstrip(".")
        if parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443):
            raise ValueError("scheme or authority")
        if not any(hostname == domain or hostname.endswith("." + domain) for domain in MEDIA_DOMAINS):
            raise ValueError("domain")
        if "\\" in url or any(ord(c) < 32 for c in url):
            raise ValueError("characters")
    except ValueError as exc:
        raise AppError("UNSAFE_URL", "视频地址不在支持的公开资源范围内。") from exc
    try:
        addresses = list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)))
    except OSError as exc:
        raise AppError("NETWORK_ERROR", "暂时无法连接视频服务器，请检查网络后重试。", 502) from exc
    if not addresses:
        raise AppError("NETWORK_ERROR", "暂时无法连接视频服务器，请检查网络后重试。", 502)
    try:
        if any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise ValueError("non-public address")
    except ValueError as exc:
        raise AppError("UNSAFE_URL", "视频地址不在支持的公开资源范围内。") from exc
    return parts, hostname, addresses


def open_media(url: str, headers: dict[str, str], timeout: int = 20):
    """Returns response and connection; caller must close both. Validates each redirect."""
    current = url
    for _ in range(6):
        parts, host, addresses = public_destination(current)
        connection = http.client.HTTPSConnection(host, timeout=timeout, context=ssl.create_default_context())
        # Keep hostname for SNI/certificate validation, connect only to checked IPs.
        def pinned_connection(address, timeout=timeout, source_address=None, **kwargs):
            last = None
            for ip in addresses:
                try:
                    return socket.create_connection((ip, 443), timeout, source_address)
                except OSError as exc:
                    last = exc
            raise last or OSError("No destination")
        connection._create_connection = pinned_connection
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        safe_headers = {k: v for k, v in headers.items() if k.lower() in {"user-agent", "referer", "accept"}}
        safe_headers["Accept-Encoding"] = "identity"
        try:
            connection.request("GET", path, headers=safe_headers)
            response = connection.getresponse()
        except Exception:
            connection.close()
            raise
        if response.status in (301, 302, 303, 307, 308):
            target = response.getheader("Location")
            response.close()
            connection.close()
            if not target:
                raise AppError("DOWNLOAD_REDIRECT", "视频服务器返回了无效跳转。", 502)
            current = urljoin(current, target)
            continue
        return response, connection
    raise AppError("DOWNLOAD_REDIRECT", "视频地址跳转次数过多，请重新解析。", 502)
