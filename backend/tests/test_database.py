from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.errors import AppError
from app.storage.database import Store


@pytest.fixture
def store(tmp_path):
    value = Store(tmp_path / "test.db")
    value.initialize()
    return value


def test_atomic_claim_does_not_run_same_task_twice(store):
    tasks = [store.create(f"share {i}") for i in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims = list(pool.map(lambda _: store.claim(), range(12)))
    ids = [task["id"] for task in claims if task]
    assert len(ids) == 8
    assert set(ids) == {task["id"] for task in tasks}


def test_cancel_wins_against_late_completion(store):
    created = store.create("share")
    store.claim()
    store.cancel(created["id"])
    assert not store.update(created["id"], status="completed", progress=100, file_name="late.mp4")
    assert store.get(created["id"])["status"] == "cancelled"


def test_restart_interrupts_running_but_preserves_queue_and_completed(store):
    running = store.create("running")
    store.claim()
    queued = store.create("queued")
    done = store.create("done")
    store.update(done["id"], allowed=("queued",), status="completed")
    assert store.recover() == 1
    assert store.get(running["id"])["status"] == "interrupted"
    assert store.get(queued["id"])["status"] == "queued"
    assert store.get(done["id"])["status"] == "completed"


def test_retry_preserves_original_and_selected_format(store):
    original = store.create("source", "high-quality")
    with pytest.raises(AppError):
        store.retry(original["id"])
    store.cancel(original["id"])
    retry = store.retry(original["id"])
    assert retry["id"] != original["id"]
    assert retry["source_text"] == "source"
    assert retry["format_id"] == "high-quality"
    assert retry["status"] == "queued"
    assert store.get(original["id"])["status"] == "cancelled"


def test_queue_limit_is_enforced(store):
    store.create("first", max_active=1)
    with pytest.raises(AppError) as error:
        store.create("second", max_active=1)
    assert error.value.code == "QUEUE_FULL"
