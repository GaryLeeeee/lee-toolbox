from __future__ import annotations

from copy import deepcopy
from email.message import Message
import json
import socket
import urllib.error
import urllib.request
from unittest.mock import Mock

import pytest

from app.providers import xiaohongshu as xhs


NOTE_ID = "6abd291e000000001c01d302"
PUBLIC_DNS = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("104.16.0.1", 443))]


def photo(**extra):
    return {"fileId": "1040testimage", "width": 2160, "height": 2880, **extra}


def note(**extra):
    return {
        "id": NOTE_ID, "type": "normal", "title": "undefined 保持原文",
        "user": {"nickname": "作者"}, "imageList": [photo()], **extra,
    }


def stream(**extra):
    return {
        "masterUrl": "http://sns-video-v6.xhscdn.com/stream/motion.mp4?sign=secret",
        "backupUrls": ["http://sns-bak-v1.xhscdn.com/stream/motion.mp4"],
        "width": 1080, "height": 1440, "duration": 2947,
        "videoCodec": "h264", "avgBitrate": 1300000, **extra,
    }


@pytest.mark.parametrize("text", [
    f"分享文案 https://www.xiaohongshu.com/explore/{NOTE_ID}。",
    f"https://www.xiaohongshu.com/discovery/item/{NOTE_ID}?xsec_token=valid",
])
def test_direct_note_uses_mobile_page_and_preserves_share_query(text):
    client = xhs._Client()
    client.request = Mock(side_effect=AssertionError("direct note needs no redirect"))
    note_id, url = client.note_url(text)
    assert note_id == NOTE_ID
    assert f"/discovery/item/{NOTE_ID}" in url
    assert ("xsec_token=valid" in url) == ("xsec_token=valid" in text)


def test_markdown_escaped_share_scheme_and_separate_line_break():
    share = (
        "Spider-Man🕸️(别问了，不发图) 纽约需要它的英雄 "
        r"https\://xhslink.cn/o/5quExjFgAjT " + "\\\n"
        "内容复制后，前往【小红书】直接打开笔记。"
    )
    assert xhs._share_url(share) == "https://xhslink.cn/o/5quExjFgAjT"


def test_markdown_escaped_direct_link_preserves_query():
    client = xhs._Client()
    client.request = Mock(side_effect=AssertionError("direct note needs no redirect"))
    assert client.note_url(r"HTTPS\://www.xiaohongshu.com/explore/" + NOTE_ID + "?xsec_token=valid。") == (
        NOTE_ID, f"https://www.xiaohongshu.com/discovery/item/{NOTE_ID}?xsec_token=valid",
    )


@pytest.mark.parametrize("url", [
    r"https\://xhslink.cn.evil.test/o/example",
    r"https\://evil.test@xhslink.cn/o/example",
    r"https\://xhslink.cn@evil.test/o/example",
    r"https\://evil.test\@xhslink.cn/o/example",
    r"https\://xhslink.cn\@evil.test/o/example",
    r"https\://xhslink.cn:8080/o/example",
    r"https\://xhslink.cn/o/exa\mple",
    r"http\://xhslink.cn/o/example",
])
def test_markdown_normalization_does_not_relax_url_validation(url):
    with pytest.raises(xhs.ProviderError):
        xhs._share_url(url)


@pytest.mark.parametrize("url", [
    "https://www.xiaohongshu.com.evil.test/explore/" + NOTE_ID,
    "https://evil.test@www.xiaohongshu.com/explore/" + NOTE_ID,
    "https://www.xiaohongshu.com@evil.test/explore/" + NOTE_ID,
    "https://www.xiaohongshu.com:8080/explore/" + NOTE_ID,
    "http://www.xiaohongshu.com/explore/" + NOTE_ID,
    "https://www.xiaohongshu.com/user/profile/" + NOTE_ID,
    "https://localhost/explore/" + NOTE_ID,
])
def test_rejects_unrelated_or_unsafe_share_urls(url):
    with pytest.raises(xhs.ProviderError):
        xhs._Client().note_url(url)


def test_short_link_upgrades_official_http_redirect_without_http_request():
    headers = Message()
    headers["Location"] = f"http://www.xiaohongshu.com/discovery/item/{NOTE_ID}?xsec_token=valid"
    client = xhs._Client()
    client.opener.open = Mock(side_effect=urllib.error.HTTPError(
        "https://xhslink.cn/o/example", 302, "Found", headers, None,
    ))
    assert client.note_url("分享 https://xhslink.cn/o/example！") == (
        NOTE_ID, f"https://www.xiaohongshu.com/discovery/item/{NOTE_ID}?xsec_token=valid",
    )
    assert client.opener.open.call_count == 1


def test_redirect_to_private_or_unrelated_host_is_rejected_before_request():
    headers = Message()
    headers["Location"] = "http://127.0.0.1/private"
    client = xhs._Client()
    client.opener.open = Mock(side_effect=urllib.error.HTTPError(
        "https://xhslink.cn/o/example", 302, "Found", headers, None,
    ))
    with pytest.raises(xhs.ProviderError):
        client.note_url("https://xhslink.cn/o/example")
    assert client.opener.open.call_count == 1


def test_media_url_requires_official_https_and_public_dns(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: PUBLIC_DNS)
    assert xhs.validate_media_url("https://sns-img-bd.xhscdn.com/image")
    for url in ["https://xhscdn.com.evil.test/image", "http://sns-img-bd.xhscdn.com/image", "https://www.xiaohongshu.com/image"]:
        with pytest.raises(xhs.ProviderError):
            xhs.validate_media_url(url)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
    ])
    with pytest.raises(xhs.ProviderError, match="非公开"):
        xhs.validate_media_url("https://sns-img-bd.xhscdn.com/image")


def test_transport_pins_checked_ip_preserving_sni_hostname(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: PUBLIC_DNS)
    connected = []
    sentinel = object()
    monkeypatch.setattr(socket, "create_connection", lambda address, timeout, source: connected.append(address) or sentinel)
    handler = xhs._PinnedHTTPSHandler()

    def do_open(factory, req, **kwargs):
        connection = factory("www.xiaohongshu.com", timeout=2, **kwargs)
        assert connection.host == "www.xiaohongshu.com"
        return connection._create_connection((connection.host, 443), 2, None)

    monkeypatch.setattr(handler, "do_open", do_open)
    assert handler.https_open(urllib.request.Request(f"https://www.xiaohongshu.com/explore/{NOTE_ID}")) is sentinel
    assert connected == [("104.16.0.1", 443)]


def test_initial_state_preserves_strings_and_normalizes_only_undefined_literals():
    html = '<script>window.__INITIAL_STATE__={"missing":undefined,"title":"undefined and \\\"undefined\\\"","nested":[undefined]};</script>'
    assert xhs._initial_state(html) == {
        "missing": None, "title": 'undefined and "undefined"', "nested": [None],
    }


@pytest.mark.parametrize("raw", [
    '{"x":(function(){return 1})()}', '{};alert(1)', '{"x":NaN}',
])
def test_initial_state_never_accepts_javascript(raw):
    with pytest.raises(xhs.ProviderError):
        xhs._initial_state(f"<script>window.__INITIAL_STATE__={raw}</script>")


def test_mobile_and_desktop_note_identity_must_match():
    assert xhs._find_note({"noteData": {"data": {"noteData": note()}}}, NOTE_ID)["id"] == NOTE_ID
    assert xhs._find_note({"note": {"noteDetailMap": {NOTE_ID: {"note": note()}}}}, NOTE_ID)["id"] == NOTE_ID
    with pytest.raises(xhs.ProviderError, match="不一致"):
        xhs._find_note({"noteData": {"data": {"noteData": note(id="0" * 24)}}}, NOTE_ID)


def test_images_use_original_keys_never_watermarked_h5_url():
    item = photo(url="https://sns-webpic-qc.xhscdn.com/date/sign/1040testimage!h5_1080jpg")
    result = xhs._parse_note(note(imageList=[item]), NOTE_ID)
    assert result.assets[0].image_urls[0] == "https://sns-img-bd.xhscdn.com/1040testimage"
    assert result.assets[0].available
    assert (result.assets[0].width, result.assets[0].height) == (2160, 2880)
    del item["fileId"]
    assert xhs._parse_note(note(imageList=[item]), NOTE_ID).assets[0].image_urls == result.assets[0].image_urls


def test_live_photo_splits_independent_original_image_and_clean_video():
    result = xhs._parse_note(note(imageList=[photo(livePhoto=True, stream={"h265": [stream(hasWatermark=False)]})]), NOTE_ID)
    still, video = result.assets
    assert still.kind == "image" and video.kind == "video"
    assert still.available and video.available and still.id != video.id
    assert still.watermark_status == video.watermark_status == "none"
    assert video.duration == 2.947 and still.duration is None
    assert len(still.image_urls) == 2 and not still.video_urls
    assert len(video.video_urls) == 2
    assert all(url.startswith("https://") for url in video.video_urls)
    assert "暂不支持直接导出 Live Photo" in "".join(result.warnings)


def test_web_livephoto_19_exports_video_with_explicit_watermark_status():
    result = xhs._parse_note(note(imageList=[photo(livePhoto=True, stream={"h264": [
        stream(streamType=19, streamDesc="WEB_LIVEPHOTO_19", hasWatermark=False),
    ]})]), NOTE_ID)
    still, video = result.assets
    assert video.kind == "video" and video.available and video.video_urls
    assert video.watermark_status == "present"
    assert "导出会保留水印" in "".join(result.warnings)
    assert still.kind == "image" and still.available and still.id != video.id
    assert still.label == "Live 图 1 · 静态原图"
    assert still.watermark_status == "none" and not still.video_urls
    assert xhs.public_note(result)["assets"][1]["watermark_status"] == "present"


def test_live_missing_motion_is_explicitly_unavailable():
    still, video = xhs._parse_note(note(imageList=[photo(livePhoto=True)]), NOTE_ID).assets
    assert still.available and still.kind == "image"
    assert video.kind == "video" and not video.available
    assert "动态片段" in video.unavailable_reason


def test_unknown_stream_cannot_claim_no_watermark_based_on_codec():
    result = xhs._parse_note(note(imageList=[photo(livePhoto=True, stream={"h265": [stream(videoCodec="h265")]})]), NOTE_ID)
    asset = result.assets[1]
    assert asset.available and asset.video_urls and asset.watermark_status == "unknown"
    assert "水印情况未确认" in "".join(result.warnings)


def test_live_video_remains_available_without_original_image():
    still, video = xhs._parse_note(note(imageList=[photo(fileId=None, livePhoto=True,
        stream={"h264": [stream(streamType=19)]})]), NOTE_ID).assets
    assert not still.available and not still.image_urls
    assert video.available and video.video_urls and video.watermark_status == "present"


def test_clean_candidate_wins_over_larger_watermarked_and_unknown_streams():
    candidates = [stream(width=4000, hasWatermark=True), stream(width=3000),
                  stream(width=720, hasWatermark=False, masterUrl="https://sns-video-v6.xhscdn.com/clean.mp4")]
    video = xhs._parse_note(note(imageList=[photo(livePhoto=True, stream={"h264": candidates})]), NOTE_ID).assets[1]
    assert video.video_urls[0].endswith("/clean.mp4") and video.watermark_status == "none"
    assert video.width == 720


def test_known_web19_path_cannot_be_mislabeled_clean_with_missing_type():
    video = xhs._parse_note(note(imageList=[photo(livePhoto=True, stream={"EF4": [stream(
        masterUrl="https://sns-video-v6.xhscdn.com/stream/1/10/19/clip_19.mp4", hasWatermark=False,
    )]})]), NOTE_ID).assets[1]
    assert video.available and video.watermark_status == "present"


def test_known_web19_original_url_or_backup_cannot_be_mislabeled_clean():
    web19 = "https://sns-video-v6.xhscdn.com/stream/1/10/19/clip_19.mp4"
    original = xhs._parse_note(note(type="video", video={"originVideoUrl": web19}), NOTE_ID).assets[0]
    assert original.available and original.watermark_status == "present"
    backup = xhs._parse_note(note(type="video", video={"media": {"stream": {"h264": [
        stream(masterUrl="https://evil.test/invalid", backupUrls=[web19], hasWatermark=False),
    ]}}}), NOTE_ID).assets[0]
    assert backup.video_urls == [web19] and backup.watermark_status == "present"


@pytest.mark.parametrize("description", ["NO_WATERMARK", "WITHOUT_WATERMARK", "WEB_NO_WATERMARK_HD"])
@pytest.mark.parametrize("flags", [{}, {"hasWatermark": False}])
def test_explicit_no_watermark_description_is_clean_evidence(description, flags):
    candidate = stream(streamDesc=description, **flags)
    urls, _, watermarked = xhs._clean_streams({"h264": [candidate]})
    assert urls and not watermarked


@pytest.mark.parametrize("extra", [
    {"hasWatermark": True},
    {"streamType": 19, "hasWatermark": False},
    {"streamDesc": "WEB_LIVEPHOTO_19_NO_WATERMARK", "hasWatermark": False},
    {"streamDesc": "NO_WATERMARK_WITH_WATERMARK", "hasWatermark": False},
])
def test_no_watermark_description_does_not_override_known_watermark(extra):
    candidate = stream(**{"streamDesc": "NO_WATERMARK", **extra})
    urls, _, watermarked = xhs._clean_streams({"h264": [candidate]})
    assert not urls and watermarked


def test_storage_keys_cannot_change_authority_or_escape_path():
    for key in ["../escape", "original/../../escape", "//evil.test/image", "https://evil.test/image", "bad?token=secret"]:
        asset = xhs._parse_note(note(imageList=[photo(fileId=key)]), NOTE_ID).assets[0]
        assert not asset.available and not asset.image_urls


def test_original_nested_live_data_and_snake_case_stream_are_supported():
    item = photo(live_photo={"consumer": {"origin_video_key": "original.mp4"}})
    original = xhs._parse_note(note(imageList=[item]), NOTE_ID).assets[1]
    assert original.available and original.watermark_status == "none"
    assert original.video_urls == ["https://sns-video-bd.xhscdn.com/original.mp4"]
    item = photo(live_photo={"media": {"stream": {"h265": [{
        "master_url": "http://sns-video-v6.xhscdn.com/original.mp4", "has_watermark": False,
    }]}}})
    assert xhs._parse_note(note(imageList=[item]), NOTE_ID).assets[1].video_urls == [
        "https://sns-video-v6.xhscdn.com/original.mp4",
    ]


def test_video_media_v2_can_supply_explicit_clean_stream_and_best_dimensions():
    result = xhs._parse_note(note(type="video", video={"mediaV2": [{"stream": {"h265": [
        stream(width=720, height=960, hasWatermark=False),
        stream(width=1440, height=1920, hasWatermark=False),
    ]}}]}), NOTE_ID)
    assert result.assets[0].available
    assert (result.assets[0].width, result.assets[0].height) == (1440, 1920)


def test_mobile_author_uses_nickname_camel_case():
    assert xhs._parse_note(note(user={"nickName": "作者"}), NOTE_ID).author == "作者"


def test_video_uses_origin_not_cover_and_drops_untrusted_streams():
    result = xhs._parse_note(note(type="video", video={
        "consumer": {"originVideoKey": "original/abc.mp4"},
        "media": {"width": 1080, "height": 1920, "stream": {"h264": [stream()]}},
    }), NOTE_ID)
    assert len(result.assets) == 1
    asset = result.assets[0]
    assert asset.kind == "video" and asset.available
    assert asset.video_urls == ["https://sns-video-bd.xhscdn.com/original/abc.mp4"]
    assert (asset.width, asset.height) == (1080, 1920)
    result = xhs._parse_note(note(type="video", video={"media": {"stream": {"h264": [
        stream(masterUrl="https://evil.test/video.mp4", backupUrls=[], hasWatermark=False),
    ]}}}), NOTE_ID)
    assert not result.assets[0].available


def test_asset_ids_ignore_signatures_and_public_output_hides_upstream_urls():
    original = note(imageList=[photo(livePhoto=True, stream={"h264": [stream(hasWatermark=False)]})])
    changed = deepcopy(original)
    changed["imageList"][0]["stream"]["h264"][0]["masterUrl"] = "https://sns-video-v99.xhscdn.com/new?sign=different"
    a = xhs._parse_note(original, NOTE_ID)
    b = xhs._parse_note(changed, NOTE_ID)
    assert [item.id for item in a.assets] == [item.id for item in b.assets]
    public = xhs.public_note(a)
    assert "secret" not in json.dumps(public)
    assert "headers" not in public
    assert all("image_urls" not in item and "video_urls" not in item and item["preview_url"] is None for item in public["assets"])


def test_resolve_fetches_and_parses_mobile_page(monkeypatch):
    request = Mock(return_value=(
        ('<script>window.__INITIAL_STATE__=' + json.dumps({"noteData": {"data": {"noteData": note()}}}) + '</script>').encode(),
        f"https://www.xiaohongshu.com/discovery/item/{NOTE_ID}",
    ))
    monkeypatch.setattr(xhs._Client, "request", request)
    result = xhs.resolve(f"https://www.xiaohongshu.com/explore/{NOTE_ID}")
    assert result.id == NOTE_ID and len(result.assets) == 1
    assert request.call_count == 1


def test_overall_resolve_deadline_is_enforced():
    client = xhs._Client()
    client.deadline = 0
    client.opener.open = Mock()
    with pytest.raises(xhs.ProviderError, match="超时"):
        client.request("https://xhslink.cn/o/example")
    client.opener.open.assert_not_called()
