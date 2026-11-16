import socket
from unittest.mock import patch

import pytest

from app.core.errors import AppError
from app.core.security import public_destination, open_media


def address(ip):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]


@pytest.mark.parametrize("url", ["http://v.douyinvod.com/video", "https://127.0.0.1/video", "https://evil.com/video",
                                  "https://v.douyinvod.com:8080/video", "https://user:pass@v.douyinvod.com/video",
                                  "https://v.douyinvod.com.evil.com/video"])
def test_rejects_untrusted_destinations_before_dns(url):
    with patch("app.core.security.socket.getaddrinfo") as dns, pytest.raises(AppError):
        public_destination(url)
    dns.assert_not_called()


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "192.168.0.1", "::1"])
def test_rejects_private_dns_answers(ip):
    with patch("app.core.security.socket.getaddrinfo", return_value=address(ip)), pytest.raises(AppError):
        public_destination("https://v.douyinvod.com/video")


def test_safe_dns_answer_is_returned_for_pinned_connection():
    with patch("app.core.security.socket.getaddrinfo", return_value=address("8.8.8.8")):
        parts, host, ips = public_destination("https://v.douyinvod.com/video")
    assert ips == ["8.8.8.8"] and host == "v.douyinvod.com"


def test_redirect_is_revalidated_before_next_request():
    class Response:
        status = 302
        def getheader(self, name):
            return "http://127.0.0.1/internal"
        def close(self):
            pass
    class Connection:
        calls = 0
        def __init__(self, *args, **kwargs):
            type(self).calls += 1
        def request(self, *args, **kwargs):
            pass
        def getresponse(self):
            return Response()
        def close(self):
            pass
    with patch("app.core.security.socket.getaddrinfo", return_value=address("8.8.8.8")), patch("app.core.security.http.client.HTTPSConnection", Connection):
        with pytest.raises(AppError):
            open_media("https://v.douyinvod.com/video", {})
    assert Connection.calls == 1


def test_dns_failure_is_network_error_not_unsafe_url():
    with patch("app.core.security.socket.getaddrinfo", side_effect=socket.gaierror(socket.EAI_AGAIN, "temporary failure")):
        with pytest.raises(AppError) as error:
            public_destination("https://v.douyinvod.com/video")
    assert error.value.code == "NETWORK_ERROR"
    assert error.value.status_code == 502


def test_download_falls_back_to_next_cdn_after_transient_dns_failure(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from app.core.settings import Settings
    from app.services.downloader import download_media

    class Response:
        status = 200
        def __init__(self):
            self.content = [b"video", b""]
        def getheader(self, name):
            return {"Content-Type": "video/mp4", "Content-Length": "5"}.get(name)
        def read1(self, size):
            return self.content.pop(0)
        def close(self):
            pass

    class Connection:
        hosts = []
        def __init__(self, host, **kwargs):
            self.hosts.append(host)
        def request(self, *args, **kwargs):
            pass
        def getresponse(self):
            return Response()
        def close(self):
            pass

    urls = ["https://first.douyinvod.com/video", "https://second.douyinvod.com/video"]
    media_format = SimpleNamespace(size_bytes=5, urls=urls)
    settings = Settings(tmp_path, tmp_path / "frontend", False)
    destination = tmp_path / "result.part"
    answers = [socket.gaierror(socket.EAI_AGAIN, "temporary failure"), address("8.8.8.8")]
    with patch("app.core.security.socket.getaddrinfo", side_effect=answers), patch("app.core.security.http.client.HTTPSConnection", Connection):
        result = download_media(media_format, {}, destination, Mock(), "task", settings, lambda: None)
    assert result == 5 and destination.read_bytes() == b"video"
    assert Connection.hosts == ["second.douyinvod.com"]
