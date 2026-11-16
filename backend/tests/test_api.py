from pathlib import Path
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LEE_TOOLBOX_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LEE_TOOLBOX_WORKER", "0")
    with TestClient(app, base_url="http://127.0.0.1:8000") as value:
        yield value


def test_task_lifecycle_api_and_unavailable_file(client):
    created = client.post("/api/tasks", json={"source_text": "https://v.douyin.com/example/"})
    assert created.status_code == 201
    task = created.json()
    assert task["status"] == "queued" and task["file_available"] is False
    assert client.get(f'/api/tasks/{task["id"]}/file').status_code == 409
    assert client.get("/api/tasks").json()["items"][0]["id"] == task["id"]
    assert client.post(f'/api/tasks/{task["id"]}/cancel').json()["status"] == "cancelled"
    retried = client.post(f'/api/tasks/{task["id"]}/retry')
    assert retried.status_code == 201
    assert retried.json()["id"] != task["id"]


def test_download_endpoint_serves_only_completed_regular_files(client, tmp_path):
    created = client.post("/api/tasks", json={"source_text": "source"}).json()
    task_id = created["id"]
    root = app.state.settings.downloads_dir
    (root / "result.mp4").write_bytes(b"video-file")
    app.state.store.update(task_id, allowed=("queued",), status="completed", file_name="result.mp4", file_size=10)
    response = client.get(f"/api/tasks/{task_id}/file")
    assert response.status_code == 200 and response.content == b"video-file"
    assert "attachment" in response.headers["content-disposition"]
    outside = tmp_path / "secret.mp4"
    outside.write_bytes(b"secret")
    (root / "link.mp4").symlink_to(outside)
    app.state.store.update(task_id, allowed=("completed",), file_name="link.mp4")
    assert client.get(f"/api/tasks/{task_id}/file").status_code == 404
    assert client.get(f"/api/tasks/{task_id}").json()["file_available"] is False
    app.state.store.update(task_id, allowed=("completed",), file_name="../../secret.mp4")
    assert client.get(f"/api/tasks/{task_id}/file").status_code == 404


def test_local_security_rejects_cross_site_and_rebinding(client):
    assert client.post("/api/tasks", json={"source_text": "source"}, headers={"Origin": "https://attacker.example"}).status_code == 403
    assert client.get("/api/tasks", headers={"Host": "attacker.example"}).status_code == 403
    assert client.post("/api/tasks", json={"source_text": "source"}, headers={"Origin": "null"}).status_code == 403
    assert client.post("/api/tasks", json={"source_text": "source"}, headers={"Origin": "http://127.0.0.1:5173"}).status_code == 201
    assert client.post("/api/tasks", json={"source_text": "source"}, headers={"Origin": "http://127.0.0.1:4000"}).status_code == 403


def test_json_errors_and_validation(client):
    assert client.get("/api/unknown").status_code == 404
    assert client.get("/api/tasks/unknown").json()["error"]["code"] == "TASK_NOT_FOUND"
    assert client.get("/api/tasks?status=anything").status_code == 422
    assert client.post("/api/tasks", json={"source_text": "  "}).status_code == 422
    assert client.post("/api/tasks", json={"source_text": "source", "file_name": "/tmp/output"}).status_code == 422


def test_static_spa_does_not_hide_api_or_allow_traversal(client, tmp_path):
    static = tmp_path / "frontend"
    static.mkdir()
    (static / "index.html").write_text("<html>Toolbox</html>")
    app.state.settings = replace(app.state.settings, frontend_dir=static)
    assert client.get("/tools/video-download").text == "<html>Toolbox</html>"
    assert client.get("/api/missing").status_code == 404
    assert client.get("/assets/missing.js").status_code == 404
    assert client.get("/%2e%2e/secret").status_code == 404


def test_resolve_does_not_expose_private_urls(client, monkeypatch):
    from app.providers import douyin
    fake = douyin.ResolvedMedia("douyin", "123", "标题", "作者", None, 5,
                               "https://www.douyin.com/video/123", [douyin.MediaFormat("f1", "720p", 720, 1280, "h264", 100, 500,
                               ["https://cdn.douyinvod.com/private-signed-url"])], {"Cookie": "private"})
    monkeypatch.setattr(douyin, "resolve", lambda text: fake)
    result = client.post("/api/media/resolve", json={"text": "share"})
    assert result.status_code == 200
    assert result.json()["formats"][0]["id"] == "f1"
    assert "private" not in result.text
