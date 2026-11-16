from dataclasses import dataclass
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    frontend_dir: Path
    worker_enabled: bool
    max_download_bytes: int = 2 * 1024 * 1024 * 1024
    download_timeout: int = 1800
    network_timeout: int = 20
    verify_timeout: int = 300
    max_active_tasks: int = 30

    @property
    def db_path(self):
        return self.data_dir / "toolbox.db"

    @property
    def downloads_dir(self):
        return self.data_dir / "downloads"

    @property
    def tmp_dir(self):
        return self.data_dir / "tmp"

    def prepare(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(exist_ok=True)
        self.tmp_dir.mkdir(exist_ok=True)


def get_settings() -> Settings:
    return Settings(
        data_dir=Path(os.environ.get("LEE_TOOLBOX_DATA_DIR", ROOT / "data")).expanduser().resolve(),
        frontend_dir=ROOT / "frontend" / "dist",
        worker_enabled=os.environ.get("LEE_TOOLBOX_WORKER", "1") != "0",
    )
