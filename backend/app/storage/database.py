import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core.errors import AppError

ACTIVE = ("queued", "resolving", "downloading", "verifying")
RUNNING = ACTIVE[1:]
RETRYABLE = ("failed", "cancelled", "interrupted")
STATUSES = ACTIVE + ("completed",) + RETRYABLE


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS tasks (
              id TEXT PRIMARY KEY, tool_id TEXT NOT NULL DEFAULT 'video-download',
              status TEXT NOT NULL, title TEXT NOT NULL, author TEXT NOT NULL DEFAULT '',
              source_text TEXT NOT NULL, format_id TEXT, format_label TEXT NOT NULL DEFAULT '自动选择',
              progress REAL NOT NULL DEFAULT 0, downloaded_bytes INTEGER NOT NULL DEFAULT 0,
              total_bytes INTEGER, speed_bps REAL, file_name TEXT, file_size INTEGER,
              error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )""")
            # Additive migrations keep existing tasks and their completed files intact.
            columns = {row["name"] for row in db.execute("PRAGMA table_info(tasks)")}
            for name, definition in {
                "tool_id": "TEXT NOT NULL DEFAULT 'video-download'",
                "asset_ids": "TEXT",
                "asset_count": "INTEGER",
                "finished_assets": "INTEGER NOT NULL DEFAULT 0",
            }.items():
                if name not in columns:
                    db.execute(f"ALTER TABLE tasks ADD COLUMN {name} {definition}")
            db.execute("CREATE INDEX IF NOT EXISTS task_status_created ON tasks(status, created_at)")

    @staticmethod
    def decode(row):
        if row is None:
            return None
        result = dict(row)
        result["error"] = json.loads(result["error"]) if result["error"] else None
        result["asset_ids"] = json.loads(result["asset_ids"]) if result.get("asset_ids") else None
        return result

    def get(self, task_id: str):
        with self.connect() as db:
            task = self.decode(db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())
        if task is None:
            raise AppError("TASK_NOT_FOUND", "任务不存在。", 404)
        return task

    def list(self, status=None):
        with self.connect() as db:
            if status:
                rows = db.execute("SELECT * FROM tasks WHERE status=? ORDER BY created_at DESC, rowid DESC LIMIT 500", (status,))
            else:
                rows = db.execute("SELECT * FROM tasks ORDER BY created_at DESC, rowid DESC LIMIT 500")
            return [self.decode(row) for row in rows]

    def create(self, source_text: str, format_id=None, max_active=30, template=None, *, tool_id="video-download", asset_ids=None):
        if tool_id not in {"video-download", "xiaohongshu-export"}:
            raise AppError("INVALID_TOOL", "不支持的工具类型。", 422)
        if asset_ids is not None and (not isinstance(asset_ids, list) or not 1 <= len(asset_ids) <= 100
                                      or any(not isinstance(item, str) or not item or len(item) > 160 for item in asset_ids)
                                      or len(set(asset_ids)) != len(asset_ids)):
            raise AppError("INVALID_SELECTION", "请选择 1 至 100 个不同的资源。", 422)
        if (tool_id == "video-download" and asset_ids is not None) or (tool_id == "xiaohongshu-export" and format_id is not None):
            raise AppError("INVALID_INPUT", "选择参数与工具类型不匹配。", 422)
        task_id, timestamp = str(uuid4()), now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('queued','resolving','downloading','verifying')").fetchone()[0]
            if count >= max_active:
                raise AppError("QUEUE_FULL", "等待处理的任务较多，请稍后再试。", 429)
            db.execute("""INSERT INTO tasks (id,tool_id,status,title,author,source_text,format_id,format_label,asset_ids,asset_count,created_at,updated_at)
                          VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (task_id, tool_id, "queued", (template or {}).get("title", "待解析笔记" if tool_id == "xiaohongshu-export" else "待解析视频"),
                          (template or {}).get("author", ""), source_text, format_id,
                          (template or {}).get("format_label", "原始资源" if tool_id == "xiaohongshu-export" else "自动选择"),
                          json.dumps(asset_ids) if asset_ids is not None else None,
                          len(asset_ids) if asset_ids is not None else None, timestamp, timestamp))
        return self.get(task_id)

    def claim(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT id FROM tasks WHERE status='queued' ORDER BY created_at, rowid LIMIT 1").fetchone()
            if row is None:
                return None
            db.execute("UPDATE tasks SET status='resolving', progress=1, updated_at=? WHERE id=? AND status='queued'", (now(), row["id"]))
            return self.decode(db.execute("SELECT * FROM tasks WHERE id=?", (row["id"],)).fetchone())

    def update(self, task_id, *, allowed=RUNNING, **fields):
        valid = {"status", "title", "author", "format_id", "format_label", "progress", "downloaded_bytes", "total_bytes", "speed_bps", "file_name", "file_size", "error", "asset_ids", "asset_count", "finished_assets"}
        if not fields or not set(fields).issubset(valid):
            raise ValueError("Invalid task update")
        if "error" in fields and fields["error"] is not None:
            fields["error"] = json.dumps(fields["error"], ensure_ascii=False)
        if "asset_ids" in fields and fields["asset_ids"] is not None:
            fields["asset_ids"] = json.dumps(fields["asset_ids"])
        fields["updated_at"] = now()
        placeholders = ",".join("?" for _ in allowed)
        with self.connect() as db:
            result = db.execute(f"UPDATE tasks SET {','.join(k+'=?' for k in fields)} WHERE id=? AND status IN ({placeholders})", (*fields.values(), task_id, *allowed))
            return result.rowcount == 1

    def cancel(self, task_id):
        task = self.get(task_id)
        if task["status"] == "cancelled":
            return task
        if not self.update(task_id, allowed=ACTIVE, status="cancelled", speed_bps=None, error=None):
            raise AppError("TASK_NOT_ACTIVE", "任务已结束，无法取消。", 409)
        return self.get(task_id)

    def retry(self, task_id, max_active=30):
        task = self.get(task_id)
        if task["status"] not in RETRYABLE:
            raise AppError("TASK_NOT_RETRYABLE", "只有失败、取消或中断的任务可以重试。", 409)
        return self.create(task["source_text"], task["format_id"], max_active, template=task,
                           tool_id=task["tool_id"], asset_ids=task.get("asset_ids"))

    def recover(self):
        with self.connect() as db:
            result = db.execute("""UPDATE tasks SET status='interrupted',speed_bps=NULL,
              error=?,updated_at=? WHERE status IN ('resolving','downloading','verifying')""",
              (json.dumps({"code": "WORKER_INTERRUPTED", "message": "服务停止导致任务中断，可重新尝试。"}, ensure_ascii=False), now()))
            return result.rowcount
