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
            db.execute("CREATE INDEX IF NOT EXISTS task_status_created ON tasks(status, created_at)")

    @staticmethod
    def decode(row):
        if row is None:
            return None
        result = dict(row)
        result["error"] = json.loads(result["error"]) if result["error"] else None
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

    def create(self, source_text: str, format_id=None, max_active=30, template=None):
        task_id, timestamp = str(uuid4()), now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('queued','resolving','downloading','verifying')").fetchone()[0]
            if count >= max_active:
                raise AppError("QUEUE_FULL", "等待处理的任务较多，请稍后再试。", 429)
            db.execute("""INSERT INTO tasks (id,status,title,author,source_text,format_id,format_label,created_at,updated_at)
                          VALUES (?,?,?,?,?,?,?,?,?)""", (task_id, "queued", (template or {}).get("title", "待解析视频"),
                          (template or {}).get("author", ""), source_text, format_id,
                          (template or {}).get("format_label", "自动选择"), timestamp, timestamp))
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
        valid = {"status", "title", "author", "format_id", "format_label", "progress", "downloaded_bytes", "total_bytes", "speed_bps", "file_name", "file_size", "error"}
        if not fields or not set(fields).issubset(valid):
            raise ValueError("Invalid task update")
        if "error" in fields and fields["error"] is not None:
            fields["error"] = json.dumps(fields["error"], ensure_ascii=False)
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
        return self.create(task["source_text"], task["format_id"], max_active, template=task)

    def recover(self):
        with self.connect() as db:
            result = db.execute("""UPDATE tasks SET status='interrupted',speed_bps=NULL,
              error=?,updated_at=? WHERE status IN ('resolving','downloading','verifying')""",
              (json.dumps({"code": "WORKER_INTERRUPTED", "message": "服务停止导致任务中断，可重新尝试。"}, ensure_ascii=False), now()))
            return result.rowcount
