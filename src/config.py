from __future__ import annotations

import os
import sys
from pathlib import Path


def env_path(name: str, default: Path) -> Path:
    return Path(os.path.expanduser(os.getenv(name, str(default)))).resolve()


def env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def env_list(name: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    return tuple(item.strip().strip("/") for item in raw.split(",") if item.strip())


PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = Path(__file__).resolve().parent
APP_HOME = env_path("SYNC_APP_HOME", Path.home() / ".local/share/115-sync-console")
DOWNLOAD_DIR = env_path("SYNC_DOWNLOAD_DIR", Path.home() / "Downloads/115")
COOKIE_FILE = env_path("SYNC_COOKIE_FILE", APP_HOME / "cookies.txt")

ROOT_CID = os.getenv("SYNC_ROOT_CID", "").strip()
ROOT_NAME = os.getenv("SYNC_ROOT_NAME", "115").strip().strip("/") or "115"
INCLUDE_PREFIX = os.getenv("SYNC_INCLUDE_PREFIX", "").strip().strip("/")
EXCLUDED_PREFIXES = env_list("SYNC_EXCLUDE_PREFIXES")
PRIORITY_KEYWORDS = env_list("SYNC_PRIORITY_KEYWORDS")

DASHBOARD_HOST = os.getenv("SYNC_DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_PORT = env_int("SYNC_DASHBOARD_PORT", 8090)
ADMIN_TOKEN = os.getenv("SYNC_ADMIN_TOKEN", "").strip()

FILE_WORKERS = env_int("SYNC_FILE_WORKERS", 4)
RANGE_WORKERS = env_int("SYNC_RANGE_WORKERS", 3)
PART_CHUNK_MIB = env_int("SYNC_PART_CHUNK_MIB", 256)
LIST_PAGE_SIZE = env_int("SYNC_LIST_PAGE_SIZE", 32)
SCAN_PAGE_DELAY = env_int("SYNC_SCAN_PAGE_DELAY", 8, minimum=0)
SCAN_DIR_DELAY = env_int("SYNC_SCAN_DIR_DELAY", 20, minimum=0)

PYTHON_BIN = os.getenv("SYNC_PYTHON_BIN", sys.executable)
ASSET_DIR = env_path("SYNC_ASSET_DIR", PROJECT_DIR / "assets")

MANIFEST = APP_HOME / "manifest.jsonl"
SCAN_MANIFEST = APP_HOME / "manifest.next.jsonl"
SCAN_STATE = APP_HOME / "scan_state.json"
SCAN_LOG = APP_HOME / "scanner.log"
SCAN_PID = APP_HOME / "scanner.pid"
SCAN_NOHUP = APP_HOME / "scanner.nohup"

DOWNLOAD_STATE = APP_HOME / "download_state.json"
DOWNLOAD_LOCK = APP_HOME / "download_state.lock"
DOWNLOAD_LOG = APP_HOME / "downloader.log"
DOWNLOAD_PID = APP_HOME / "downloader.pid"
DOWNLOAD_NOHUP = APP_HOME / "downloader.nohup"


def ensure_runtime_dirs() -> None:
    APP_HOME.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def is_excluded(relpath: str) -> bool:
    normalized = str(relpath or "").strip().strip("/")
    return any(
        normalized == prefix or normalized.startswith(prefix + "/")
        for prefix in EXCLUDED_PREFIXES
    )


def strip_remote_root(relpath: str) -> str:
    normalized = str(relpath or "").strip().strip("/")
    if normalized == ROOT_NAME:
        return ""
    prefix = ROOT_NAME + "/"
    return normalized[len(prefix):] if normalized.startswith(prefix) else normalized
