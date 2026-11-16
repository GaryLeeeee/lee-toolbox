from __future__ import annotations

from email.message import Message
import socket
import urllib.error
from unittest.mock import Mock

import pytest

from app.providers import douyin

VIDEO_ID = "7444165186107297074"
PUBLIC_DNS = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("104.16.0.1", 443))]


def address(width=720, height=1280, file_hash="a", query="old"):
    return {
        "width": width, "height": height, "file_hash": file_hash,
        "data_size": 123456,
        "url_list": [f"https://v1.douyinvod.com/play/{file_hash}?token={query}"],
    }


def detail():
    return {
        "aweme_id": VIDEO_ID, "desc": "示例作品", "author": {"nickname": "示例作者"},
        "video": {
            "width": 2160, "height": 3840, "duration": 66974,
            "bit_rate": [
                {"gear_name": "720_h264", "quality_type": 10, "bit_rate": 1000000,
                 "is_h265": 0, "play_addr": address()},
                {"gear_name": "720_h265", "quality_type": 15, "bit_rate": 1500000,
                 "is_h265": 1, "play_addr": address(file_hash="b")},
                {"gear_name": "540_h264", "quality_type": 20, "bit_rate": 1800000,
                 "play_addr": address(576, 1024, "c")},
            ],
            "play_addr": address(), "play_addr_h264": address(),
            "download_addr": address(file_hash="watermarked"),
        },
    }


@pytest.mark.parametrize("text", [
    f"分享作品 https://www.douyin.com/video/{VIDEO_ID} 作者",
    f"https://www.iesdouyin.com/share/video/{VIDEO_ID}/。",
    f"https://www.douyin.com/video/{VIDEO_ID}）",
])
def test_extracts_video_id_from_share_text_without_fetching_page(text):
    client = douyin._Client()
    client.request = Mock(side_effect=AssertionError("direct ID needs no fetch"))
    assert client.video_id(text) == VIDEO_ID


@pytest.mark.parametrize("url", [
    "https://localhost/video/7444165186107297074",
    "https://www.douyin.com.evil.test/video/7444165186107297074",
    "https://www.douyin.com@evil.test/video/7444165186107297074",
    "https://evil.test@www.douyin.com/video/7444165186107297074",
    "http://www.douyin.com/video/7444165186107297074",
    "https://www.douyin.com:9000/video/7444165186107297074",
    "file:///etc/passwd",
])
def test_rejects_unsafe_or_unrelated_input(url):
    with pytest.raises(douyin.ProviderError):
        douyin._Client().video_id(url)


def test_media_dns_rejects_private_addresses(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
    ])
    with pytest.raises(douyin.ProviderError, match="非公开"):
        douyin.validate_media_url("https://v1.douyinvod.com/file.mp4")


def test_validates_redirect_before_making_second_request(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: PUBLIC_DNS)
    headers = Message()
    headers["Location"] = "https://127.0.0.1/private"
    client = douyin._Client()
    client.opener.open = Mock(side_effect=urllib.error.HTTPError(
        "https://v.douyin.com/abc/", 302, "Found", headers, None,
    ))
    with pytest.raises(douyin.ProviderError):
        client.video_id("https://v.douyin.com/abc/")
    assert client.opener.open.call_count == 1


def test_short_link_redirect_extracts_id(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: PUBLIC_DNS)
    headers = Message()
    headers["Location"] = f"https://www.iesdouyin.com/share/video/{VIDEO_ID}/?tracking=ignored"
    client = douyin._Client()
    client.opener.open = Mock(side_effect=urllib.error.HTTPError(
        "https://v.douyin.com/abc/", 302, "Found", headers, None,
    ))
    assert client.video_id("https://v.douyin.com/abc/") == VIDEO_ID
    assert client.opener.open.call_count == 1


def test_formats_use_stream_dimensions_sort_and_deduplicate():
    result = douyin._parse_detail(detail(), VIDEO_ID)
    assert len(result.formats) == 3
    assert [(f.width, f.codec) for f in result.formats] == [(720, "h264"), (720, "h265"), (576, "h264")]
    assert result.duration == 66.974
    assert all("watermarked" not in url for f in result.formats for url in f.urls)
    assert all(f.width != 2160 for f in result.formats)


def test_format_ids_survive_cdn_signature_and_url_changes():
    original = detail()
    changed = detail()
    for variant in changed["video"]["bit_rate"]:
        variant["play_addr"]["url_list"] = ["https://v99.douyinvod.com/new-route?token=new"]
    first = douyin._parse_detail(original, VIDEO_ID)
    second = douyin._parse_detail(changed, VIDEO_ID)
    assert [f.id for f in first.formats] == [f.id for f in second.formats]


def test_public_media_does_not_leak_signed_urls_or_headers():
    result = douyin.public_media(douyin._parse_detail(detail(), VIDEO_ID))
    assert "headers" not in result
    assert all("urls" not in f for f in result["formats"])
    assert "token=" not in repr(result)
    assert result["source_url"] == f"https://www.douyin.com/video/{VIDEO_ID}"


def test_rejects_wrong_video_and_non_video():
    with pytest.raises(douyin.ProviderError, match="不一致"):
        douyin._parse_detail({**detail(), "aweme_id": "1234567890123456789"}, VIDEO_ID)
    with pytest.raises(douyin.ProviderError, match="不是可下载"):
        douyin._parse_detail({"aweme_id": VIDEO_ID, "images": []}, VIDEO_ID)


def test_excludes_untrusted_media_hosts_and_does_not_promote_master_dimensions():
    item = detail()
    item["video"]["bit_rate"] = []
    item["video"]["play_addr_h264"] = {}
    item["video"]["play_addr"] = {"url_list": ["https://v1.douyinvod.com/file"]}
    result = douyin._parse_detail(item, VIDEO_ID)
    assert (result.formats[0].width, result.formats[0].height) == (0, 0)
    item["video"]["play_addr"] = {"url_list": ["https://example.com/file.mp4"]}
    with pytest.raises(douyin.ProviderError, match="没有找到"):
        douyin._parse_detail(item, VIDEO_ID)


def test_https_transport_connects_to_checked_ip_and_retains_hostname(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: PUBLIC_DNS)
    connected = []
    sentinel = object()

    def fake_socket(address, timeout, source_address):
        connected.append(address)
        return sentinel

    monkeypatch.setattr(socket, "create_connection", fake_socket)
    handler = douyin._PinnedHTTPSHandler()

    def fake_do_open(factory, req, **kwargs):
        connection = factory("www.douyin.com", timeout=2, **kwargs)
        assert connection.host == "www.douyin.com"
        # Even if a later DNS lookup would rebind the name, connection uses the
        # pinned literal IP rather than resolving the hostname again.
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ])
        return connection._create_connection(("www.douyin.com", 443), 2)

    monkeypatch.setattr(handler, "do_open", fake_do_open)
    import urllib.request
    result = handler.https_open(urllib.request.Request("https://www.douyin.com/"))
    assert result is sentinel
    assert connected == [("104.16.0.1", 443)]


def test_slow_response_honors_overall_deadline(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: PUBLIC_DNS)
    clock = [0.0]
    monkeypatch.setattr(douyin.time, "monotonic", lambda: clock[0])
    client = douyin._Client()
    client.deadline = 5.0

    class SlowResponse:
        headers = {}
        fp = None
        reads = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read1(self, size):
            self.reads += 1
            clock[0] += 3.0
            return b"x"

    response = SlowResponse()
    client.opener.open = Mock(return_value=response)
    with pytest.raises(douyin.ProviderError, match="超时"):
        client.request("https://www.douyin.com/")
    assert response.reads == 2
